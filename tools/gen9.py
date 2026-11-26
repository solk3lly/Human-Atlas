"""Generate Z-Anatomy regional vascular bundles (vsKa..vsTu) with clean labels and regional rules.

Rebuild notes when re-running against Z-Anatomy sk.obj:
- Verify contralateral Transverse_sinus.r (vsKv) and Axillary_vein.l (vsLe) are extracted and pass
  cls.validate_bilateral_polarity().
- Pack via import_hra.pack (ha-mesh-v2) rather than legacy v1 layer-wide uint16.
"""

import collections
import json
import re
import cls

isv = lambda b: bool(re.search(r'vein|vena|sinus|venous|plexus', b, re.I))

LAY = {
    'vsKa': 'Kepala & Leher (Arteri)',
    'vsKv': 'Kepala & Leher (Vena)',
    'vsTo': 'Toraks',
    'vsAb': 'Abdomen & Pelvis',
    'vsLe': 'Lengan & Tangan',
    'vsTu': 'Tungkai & Kaki',
}
RK = {
    'Kepala & Leher': None,
    'Toraks': 'vsTo',
    'Abdomen & Pelvis': 'vsAb',
    'Lengan & Tangan': 'vsLe',
    'Tungkai & Kaki': 'vsTu',
}

# Orphaned Z-Anatomy coronary fragments removed from vsTo because the Heart moved to HuBMAP HRA (jantung)
EXCLUDED_CORONARY_FRAGMENTS = {
    'Circumflex_artery_of_heart',
    'Right_inferolateral_branch_of_right_coronary_artery',
    'Septal_branches_of_anterior_interventricular_artery',
}

# Vessels routed explicitly to match anatomical origin/paired drainage
REGION_OVERRIDES = {
    'Subcostal_artery': 'vsAb',          # paired with Left/Right_subcostal_vein in vsAb
    'Inferior_phrenic_artery': 'vsAb',   # branch of abdominal aorta
}

GEN = {
    'artery_gen': dict(zip(
        ['desc', 'fn', 'nerve', 'blood', 'rel', 'clin'],
        [
            'Arteri membawa darah dari jantung ke jaringan; dindingnya terdiri dari tunika intima, media (otot polos dan elastin), dan adventisia. Rincian untuk pembuluh ini belum ditulis satu per satu.',
            'Menyalurkan darah beroksigen (kecuali a. pulmonalis) dengan tekanan tinggi ke organ dan jaringan yang dilayaninya.',
            'Serabut simpatis vasomotor di tunika adventisia mengatur diameter pembuluh; baroreseptor pada arteri besar tertentu.',
            'Vasa vasorum (pembuluh kecil) memberi nutrisi pada dinding arteri besar.',
            'Biasanya berjalan bersama vena dan saraf dalam berkas neurovaskular; letak tepatnya bergantung pada nama pembuluh.',
            'Aterosklerosis, aneurisma, emboli, trombosis, diseksi, dan cedera trauma; gejala bergantung pada daerah yang dipasok.',
        ],
    )),
    'vein_gen': dict(zip(
        ['desc', 'fn', 'nerve', 'blood', 'rel', 'clin'],
        [
            'Vena membawa darah kembali ke jantung; dindingnya lebih tipis dengan katup di banyak vena ekstremitas, dan sinus dura tidak berotot. Rincian untuk pembuluh ini belum ditulis satu per satu.',
            'Mengalirkan darah kembali ke jantung dengan tekanan rendah (kecuali v. pulmonalis); berfungsi pula sebagai reservoir darah.',
            'Serabut simpatis vasomotor mengatur venokonstriksi; vena dalam mengikuti persarafan struktur di dekatnya.',
            'Vasa vasorum pada vena besar.',
            'Vena dalam biasanya menyertai arteri; vena superfisial berjalan di jaringan bawah kulit.',
            'Trombosis vena dalam, varises, tromboflebitis, insufisiensi vena, trombosis sinus (pada sinus dura).',
        ],
    )),
}


def clean_vessel_label(base):
    """Convert Z-Anatomy vessel base name to clean display text without breaking balanced parentheses."""
    s = base.replace('_', ' ').strip().rstrip('.')
    if s.startswith('(') and s.endswith(')') and s.count('(') == 1 and s.count(')') == 1:
        s = s[1:-1].strip()
    return s


def normalize_vessel_base(base):
    """Normalize Z-Anatomy hyphen/underscore variants so bilateral M2/M3 segments merge into one item."""
    if base == 'Middle_cerebral_artery_(M3-segment)':
        return 'Middle_cerebral_artery_(M3_segment)'
    if base == 'Insular_branches_of_middle_cerebral_artery_(M2-segment)':
        return 'Insular_branches_of_middle_cerebral_artery_(M2)'
    return base


def vessel_target_layer(reg, base):
    """Return destination layer key for a vessel base name, or None if excluded."""
    if base in EXCLUDED_CORONARY_FRAGMENTS:
        return None
    if base in REGION_OVERRIDES:
        return REGION_OVERRIDES[base]
    return ('vsKv' if isv(base) else 'vsKa') if reg == 'Kepala & Leher' else RK[reg]


def bucket_vessels(items, chunk_size=22):
    """Group named primary vessels first, then non-redundant alphabetical buckets."""
    primary = sorted([it for it in items if it.get('l')], key=lambda o: o['n'].lower())
    other = sorted([it for it in items if not it.get('l')], key=lambda o: o['n'].lower())
    groups = []
    if primary:
        groups.append({'g': 'Pembuluh Utama', 'items': primary})
    buckets = []
    cur = []
    for o in other:
        cur.append(o)
        if len(cur) >= chunk_size:
            buckets.append(cur)
            cur = []
    if cur:
        buckets.append(cur)
    for b in buckets:
        a = b[0]['n'][:1].upper()
        z = b[-1]['n'][:1].upper()
        groups.append({'g': a if a == z else f'{a}–{z}', 'items': b})
    return groups


def main():
    import pickle
    import numpy as np
    import import_hra

    info = pickle.load(open('vs_info.pkl', 'rb'))
    L = {k: [] for k in LAY}

    def split_mesh(V, F):
        if len(V) <= import_hra.MAX_VERTICES:
            return [(V, F)]
        cs = 100000
        while True:
            out = []
            for s in range(0, len(F), cs):
                f = F[s:s + cs]
                u = np.unique(f)
                r = -np.ones(len(V), int)
                r[u] = np.arange(len(u))
                out.append((V[u], r[f]))
            if max(len(o[0]) for o in out) <= import_hra.MAX_VERTICES:
                return out
            cs //= 2

    for i, reg, nv, nf in info:
        z = np.load(f'vs/{i}.npz')
        V = z['V'].astype(np.float64)
        F = z['F'].astype(np.int64)
        used = np.unique(F)
        r = -np.ones(len(V), int)
        r[used] = np.arange(len(used))
        V = V[used]
        F = r[F]
        b = normalize_vessel_base(cls.split(cls.names[i])[0])
        k = vessel_target_layer(reg, b)
        if k is None:
            continue
        for v, f in split_mesh(V, F):
            L[k].append((cls.names[i], v, f))

    groups = {}
    tot = {}
    sd = lambda s: 'kanan & kiri' if s == {'r', 'l'} else 'kanan' if s == {'r'} else 'kiri' if s == {'l'} else 'garis tengah'
    for k, ms in L.items():
        its = collections.OrderedDict()
        for idx, (n, _v, _f) in enumerate(ms):
            b, sfx, side, t = cls.split(n)
            b = normalize_vessel_base(b)
            it = its.setdefault(b, {'p': [], 's': set()})
            it['p'].append(idx)
            if side:
                it['s'].add(side)
        items = sorted(
            [{
                'id': b,
                'n': clean_vessel_label(b),
                'l': '',
                'e': clean_vessel_label(b),
                'r': LAY[k],
                's': sd(it['s']),
                'p': it['p'],
                'd': 'vein_gen' if isv(b) else 'artery_gen',
                'g': 1,
            } for b, it in its.items()],
            key=lambda o: o['n'].lower(),
        )
        groups[k] = bucket_vessels(items)
        bundle = import_hra.pack(ms, layer=k, sidebar_groups=groups[k])
        import_hra.write_data(import_hra.ROOT / 'data' / f'atlas_{k}.json', bundle)
        tot[k] = (len(ms), len(items), sum(m[2] for m in bundle['m']['meta']))
    print(tot)
    json.dump({'g': groups, 'DET': GEN, 'LAY': LAY}, open('vs_meta.json', 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main()
