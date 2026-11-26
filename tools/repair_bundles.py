"""Lossless, idempotent repairs directly on shipped ha-mesh-v2 bundles.

Requires only Python 3 standard library (no NumPy or external 3D archives).
Preserves exact vertex bytes (zero re-quantization drift) and updates bundle +
index.html generation hashes atomically.

Repairs performed:
1. organ: Strip 12 coplanar Diaphragm.o* origin stickers causing z-fighting.
2. jantung: Split mislabeled LCx mesh [21] out of Diagonal_branches_of_lad_artery
   into Circumflex_artery_of_heart (with DET['lcx']), verified geometrically.
3. vsKa, jantung, limfonodus: Deduplicate within-mesh repeated triangles.
4. jantung, urin: Flip inverted-winding nearly-closed shells to outward CCW.
5. saraf, vsTu: Append '.r' suffix to unsuffixed right-sided bilateral meshes
   (Cochlear_nerve, Common_plantar_digital_branches_of_medial_plantar_nerve,
   Descending_branch_of_lateral_circumflex_femoral_artery).
"""

import base64
import hashlib
import json
import math
import os
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LCX_DET = {
    'desc': 'Salah satu dari dua cabang utama a. koroner kiri yang berjalan ke belakang dalam sulkus atrioventrikular (koronarius) kiri di antara atrium kiri dan ventrikel kiri.',
    'fn': 'Memasok dinding lateral dan posterolateral ventrikel kiri, atrium kiri, serta pada dominansi kiri (~10–15%) melahirkan PDA dan memasok nodus AV.',
    'nerve': 'Persarafan otonom pleksus kardiakus (simpatis dan parasimpatis n. vagus).',
    'blood': 'Cabang utama a. koroner kiri; melahirkan cabang marginal tumpul (obtuse marginal / marginal kiri) dan cabang atrial.',
    'rel': 'Sulkus koronarius kiri, sinus koronarius, v. jantung besar, atrium kiri, ventrikel kiri, katup mitral.',
    'clin': 'Infark miokard dinding lateral (elevasi ST di I, aVL, V5–V6), regurgitasi mitral iskemik, stenosis koroner (PCI/CABG).',
}

RIGHT_SUFFIX_REPAIRS = {
    'saraf': {'Cochlear_nerve', 'Common_plantar_digital_branches_of_medial_plantar_nerve'},
    'vsTu': {'Descending_branch_of_lateral_circumflex_femoral_artery'},
}

WINDING_TARGETS = {
    'jantung': {
        'Aortic_valve',
        'Circumflex_artery_of_heart.l',
        'Middle_cardiac_vein',
        'Posterior_vein_of_left_ventricle.l',
    },
    'urin': {'Minor_renal_calyx.l'},
}


def compute_gen(layer, meta, sidebar_groups):
    payload = {
        'layer': layer,
        'meta': [[row[0], row[1], row[2]] for row in meta],
        'items': [[it['id'], it['p']] for g in sidebar_groups for it in g['items']],
    }
    raw = json.dumps(payload, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:16]


def unpack_v2(bundle):
    blob = base64.b64decode(bundle['b'], validate=True)
    meshes = []
    for row in bundle['m']['meta']:
        name, nv, nf, vo, fo, enc, mn, sc = row
        vbytes = blob[vo:vo + nv * (12 if enc == 'f32' else 6)]
        fbytes = blob[fo:fo + nf * 6]
        meshes.append({
            'name': name,
            'nv': nv,
            'nf': nf,
            'enc': enc,
            'mn': list(mn),
            'sc': list(sc) if isinstance(sc, list) else sc,
            'vbytes': vbytes,
            'fbytes': fbytes,
        })
    return meshes


def repack_v2(bundle, layer, meshes, sidebar_groups):
    # Layout: all f32 vertex blocks (4-byte aligned), then u16 vertex blocks (2-byte aligned), then u16 face blocks.
    f32_buf = bytearray()
    u16_buf = bytearray()
    face_buf = bytearray()

    f32_offs = []
    u16_offs = []
    face_offs = []

    for m in meshes:
        if m['enc'] == 'f32':
            assert len(f32_buf) % 4 == 0
            f32_offs.append(len(f32_buf))
            u16_offs.append(None)
            f32_buf.extend(m['vbytes'])
        else:
            f32_offs.append(None)
            u16_offs.append(len(u16_buf))
            u16_buf.extend(m['vbytes'])
        face_offs.append(len(face_buf))
        face_buf.extend(m['fbytes'])

    u16_base = len(f32_buf)
    face_base = u16_base + len(u16_buf)

    meta = []
    for idx, m in enumerate(meshes):
        vo = f32_offs[idx] if m['enc'] == 'f32' else u16_base + u16_offs[idx]
        fo = face_base + face_offs[idx]
        meta.append([m['name'], m['nv'], m['nf'], vo, fo, m['enc'], m['mn'], m['sc']])

    blob = bytes(f32_buf) + bytes(u16_buf) + bytes(face_buf)
    gen = compute_gen(layer, meta, sidebar_groups)
    return {
        'v': 2,
        'fmt': 'ha-mesh-v2',
        'endian': 'le',
        'gen': gen,
        'b': base64.b64encode(blob).decode('ascii'),
        'm': {'mn': bundle['m']['mn'], 'sc': bundle['m']['sc'], 'meta': meta},
    }, gen


def decode_verts(m):
    nv = m['nv']
    if m['enc'] == 'f32':
        return list(struct.iter_unpack('<3f', m['vbytes']))
    mn = m['mn']
    sx, sy, sz = m['sc'] if isinstance(m['sc'], list) else (m['sc'], m['sc'], m['sc'])
    kx, ky, kz = sx / 65535.0, sy / 65535.0, sz / 65535.0
    ox, oy, oz = mn[0], mn[1], mn[2]
    return [(ox + qx * kx, oy + qy * ky, oz + qz * kz) for qx, qy, qz in struct.iter_unpack('<3H', m['vbytes'])]


def signed_volume(m):
    verts = decode_verts(m)
    tot = 0.0
    for a, b, c in struct.iter_unpack('<3H', m['fbytes']):
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        tot += ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)
    return tot / 6.0


def min_distance_mm(ma, mb):
    va = decode_verts(ma)
    vb = decode_verts(mb)
    # Sample up to 600 verts if very dense for fast deterministic check
    sa = va[::max(1, len(va) // 600)]
    sb = vb[::max(1, len(vb) // 600)]
    best = float('inf')
    for ax, ay, az in sa:
        for bx, by, bz in sb:
            d2 = (ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2
            if d2 < best:
                best = d2
    return math.sqrt(best) * 1000.0


def dedupe_repeated_faces(m):
    if m['enc'] == 'u16':
        vkeys = list(struct.iter_unpack('<3H', m['vbytes']))
    else:
        vkeys = [(round(x, 7), round(y, 7), round(z, 7)) for x, y, z in struct.iter_unpack('<3f', m['vbytes'])]

    seen = set()
    kept = bytearray()
    removed = 0
    for a, b, c in struct.iter_unpack('<3H', m['fbytes']):
        ka, kb, kc = vkeys[a], vkeys[b], vkeys[c]
        # Canonical unordered triangle key (handles both identical and flipped duplicate faces)
        if ka <= kb:
            tri_key = (ka, kb, kc) if kb <= kc else ((ka, kc, kb) if ka <= kc else (kc, ka, kb))
        else:
            tri_key = (kb, ka, kc) if ka <= kc else ((kb, kc, ka) if kb <= kc else (kc, kb, ka))
        if tri_key in seen:
            removed += 1
        else:
            seen.add(tri_key)
            kept.extend(struct.pack('<3H', a, b, c))
    if removed:
        m['fbytes'] = bytes(kept)
        m['nf'] = len(kept) // 6
    return removed


def flip_winding(m):
    out = bytearray(len(m['fbytes']))
    off = 0
    for a, b, c in struct.iter_unpack('<3H', m['fbytes']):
        struct.pack_into('<3H', out, off, a, c, b)
        off += 6
    m['fbytes'] = bytes(out)


def write_atomic(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


def main():
    html_path = ROOT / 'index.html'
    page = html_path.read_text(encoding='utf-8')
    s0 = page.index('<script>const BL = ')
    e0 = page.index('</script>', s0) + len('</script>')
    BL, _ = json.JSONDecoder().raw_decode(page.split('const BL = ', 1)[1])
    DET, _ = json.JSONDecoder().raw_decode(page.split('const DET = ', 1)[1])

    changed_bundles = {}

    # 1. organ: strip coplanar Diaphragm.o* stickers
    organ_path = ROOT / 'data' / 'atlas_organ.json'
    organ_bundle = json.loads(organ_path.read_bytes())
    organ_meshes = unpack_v2(organ_bundle)
    keep_idx = [i for i, m in enumerate(organ_meshes) if not re.match(r'^Diaphragm\.o', m['name'])]
    if len(keep_idx) != len(organ_meshes):
        dropped = len(organ_meshes) - len(keep_idx)
        remap = {old: new for new, old in enumerate(keep_idx)}
        organ_meshes = [organ_meshes[i] for i in keep_idx]
        for g in BL['organ']['g']:
            for it in g['items']:
                it['p'] = [remap[idx] for idx in it['p'] if idx in remap]
                assert it['p'], f'organ/{it["id"]} lost all meshes'
        new_bundle, new_gen = repack_v2(organ_bundle, 'organ', organ_meshes, BL['organ']['g'])
        BL['organ']['gen'] = new_gen
        changed_bundles[organ_path] = new_bundle
        print(f'[organ] Stripped {dropped} coplanar Diaphragm.o* stickers (gen={new_gen})')

    # 2. jantung: split mislabeled LCx [21] + dedupe faces + fix inverted shells
    jantung_path = ROOT / 'data' / 'atlas_jantung.json'
    jantung_bundle = json.loads(jantung_path.read_bytes())
    jantung_meshes = unpack_v2(jantung_bundle)
    jantung_changed = False

    cor_grp = next(g for g in BL['jantung']['g'] if g['g'] == 'Pembuluh Koroner')
    diag_it = next(it for it in cor_grp['items'] if it['id'] == 'Diagonal_branches_of_lad_artery')
    has_lcx = any(it['id'] == 'Circumflex_artery_of_heart' for it in cor_grp['items'])
    if not has_lcx and len(diag_it['p']) == 2:
        idx_diag, idx_lcx = diag_it['p']
        lca_idx = next(it['p'][0] for it in cor_grp['items'] if it['id'] == 'Left_coronary_artery')
        lma_idx = next(it['p'][0] for it in cor_grp['items'] if it['id'] == 'Left_marginal_artery')
        d_lca = min_distance_mm(jantung_meshes[idx_lcx], jantung_meshes[lca_idx])
        d_lma = min_distance_mm(jantung_meshes[idx_lcx], jantung_meshes[lma_idx])
        assert d_lca < 2.0 and d_lma < 2.0, f'Expected LCx near LMCA ({d_lca:.2f} mm) and LMA ({d_lma:.2f} mm)'
        jantung_meshes[idx_lcx]['name'] = 'Circumflex_artery_of_heart.l'
        diag_it['p'] = [idx_diag]
        lad_pos = next(i for i, it in enumerate(cor_grp['items']) if it['id'] == 'Anterior_interventricular_artery')
        cor_grp['items'].insert(lad_pos + 1, {
            'id': 'Circumflex_artery_of_heart',
            'n': 'Arteri Sirkumfleksa Kiri (LCx)',
            'l': 'Ramus circumflexus arteriae coronariae sinistrae',
            'e': 'Left circumflex coronary artery (LCx)',
            'r': 'Pembuluh Koroner',
            's': 'kiri',
            'p': [idx_lcx],
            'd': 'lcx',
        })
        DET['lcx'] = LCX_DET
        jantung_changed = True
        print(f'[jantung] Split mesh [{idx_lcx}] into Circumflex_artery_of_heart (d_LMCA={d_lca:.2f}mm, d_LMA={d_lma:.2f}mm)')

    j_dups = sum(dedupe_repeated_faces(m) for m in jantung_meshes)
    if j_dups:
        jantung_changed = True
        print(f'[jantung] Removed {j_dups} repeated triangles')

    for m in jantung_meshes:
        if m['name'] in WINDING_TARGETS['jantung']:
            v = signed_volume(m)
            if v < 0:
                flip_winding(m)
                jantung_changed = True
                print(f'[jantung] Flipped inverted winding on {m["name"]} (was {v:.3e}, now {signed_volume(m):.3e})')

    if jantung_changed:
        new_bundle, new_gen = repack_v2(jantung_bundle, 'jantung', jantung_meshes, BL['jantung']['g'])
        BL['jantung']['gen'] = new_gen
        changed_bundles[jantung_path] = new_bundle

    # 3. urin: flip inverted Minor_renal_calyx.l shell(s)
    urin_path = ROOT / 'data' / 'atlas_urin.json'
    urin_bundle = json.loads(urin_path.read_bytes())
    urin_meshes = unpack_v2(urin_bundle)
    urin_changed = False
    for m in urin_meshes:
        if m['name'] in WINDING_TARGETS['urin']:
            v = signed_volume(m)
            if v < 0:
                flip_winding(m)
                urin_changed = True
                print(f'[urin] Flipped inverted winding on {m["name"]} (was {v:.3e}, now {signed_volume(m):.3e})')
    if urin_changed:
        new_bundle, new_gen = repack_v2(urin_bundle, 'urin', urin_meshes, BL['urin']['g'])
        BL['urin']['gen'] = new_gen
        changed_bundles[urin_path] = new_bundle

    # 4. vsKa & limfonodus: dedupe repeated triangles
    for lk in ('vsKa', 'limfonodus'):
        p = ROOT / 'data' / f'atlas_{lk}.json'
        b = json.loads(p.read_bytes())
        ms = unpack_v2(b)
        dups = sum(dedupe_repeated_faces(m) for m in ms)
        if dups:
            nb, ng = repack_v2(b, lk, ms, BL[lk]['g'])
            BL[lk]['gen'] = ng
            changed_bundles[p] = nb
            print(f'[{lk}] Removed {dups} repeated triangles (gen={ng})')

    # 5. saraf & vsTu: append .r to unsuffixed right-sided bilateral meshes
    for lk, bases in RIGHT_SUFFIX_REPAIRS.items():
        p = ROOT / 'data' / f'atlas_{lk}.json'
        b = json.loads(p.read_bytes())
        ms = unpack_v2(b)
        renamed = 0
        for m in ms:
            if m['name'] in bases:
                verts = decode_verts(m)
                cx = sum(v[0] for v in verts) / len(verts)
                assert cx < -0.01, f'Expected {lk}/{m["name"]} on right side (X<-0.01), got {cx:.4f}'
                m['name'] = m['name'] + '.r'
                renamed += 1
        if renamed:
            nb, ng = repack_v2(b, lk, ms, BL[lk]['g'])
            BL[lk]['gen'] = ng
            changed_bundles[p] = nb
            print(f'[{lk}] Renamed {renamed} unsuffixed right mesh(es) to .r (gen={ng})')

    # Commit atomically
    for p, b in changed_bundles.items():
        write_atomic(p, json.dumps(b, separators=(',', ':'), ensure_ascii=False))
    if changed_bundles:
        new_script0 = (
            '<script>const BL = '
            + json.dumps(BL, ensure_ascii=False, separators=(',', ':'))
            + '; const DET = '
            + json.dumps(DET, ensure_ascii=False, separators=(',', ':'))
            + ';</script>'
        )
        write_atomic(html_path, page[:s0] + new_script0 + page[e0:])
        print(f'Atomically updated {len(changed_bundles)} bundles + index.html.')
    else:
        print('All bundles already clean (idempotent no-op).')


if __name__ == '__main__':
    main()
