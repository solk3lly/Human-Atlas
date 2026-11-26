"""Losslessly upgrade the 13 legacy Z-Anatomy bundles to ha-mesh-v2 with generation hashes.

For the six regional vessel layers (vsKa, vsKv, vsTo, vsAb, vsLe, vsTu), each mesh is matched back
to its exact un-degraded quantized lattice in commit bc3f6f9 so that moving vessels across regional
bundles never re-quantizes fine anatomy (restoring Central_retinal_artery from 230 -> 98 zero-area
faces in vsKa with zero extra binary bytes).
"""

import base64
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import import_hra

VESSEL_LAYERS = ('vsKa', 'vsKv', 'vsTo', 'vsAb', 'vsLe', 'vsTu')
OTHER_LEGACY_LAYERS = ('rangka', 'otot', 'saraf', 'organ', 'cerna', 'repro', 'endo')
GIT_BASE_COMMIT = 'bc3f6f9'


def decode_any_bundle(data):
    """Return list of (name, q_u16, f_u16, mn_vec3, sc_vec3, verts_f64)."""
    blob = base64.b64decode(data['b'])
    ver = data.get('v', 1)
    out = []
    if ver == 2:
        for name, nv, nf, vo, fo, enc, mn, sc in data['m']['meta']:
            mn_a = np.asarray(mn, dtype=np.float64)
            sc_a = np.asarray(sc if isinstance(sc, list) else [sc, sc, sc], dtype=np.float64)
            f = np.frombuffer(blob, dtype='<u2', count=3 * nf, offset=fo).reshape(nf, 3).copy()
            if enc == 'u16':
                q = np.frombuffer(blob, dtype='<u2', count=3 * nv, offset=vo).reshape(nv, 3).copy()
                v = mn_a + q.astype(np.float64) * (sc_a / 65535.0)
                out.append((name, q, f, mn_a, sc_a, v))
            else:
                v = np.frombuffer(blob, dtype='<f4', count=3 * nv, offset=vo).reshape(nv, 3).astype(np.float64)
                out.append((name, None, f, mn_a, sc_a, v))
    else:
        mn_a = np.asarray(data['m']['mn'], dtype=np.float64)
        sc_f = float(data['m']['sc'])
        sc_a = np.array([sc_f, sc_f, sc_f], dtype=np.float64)
        words = np.frombuffer(blob, dtype='<u2')
        for name, nv, nf, vo, fo in data['m']['meta']:
            q = words[vo:vo + 3 * nv].reshape(nv, 3).copy()
            f = words[fo:fo + 3 * nf].reshape(nf, 3).copy()
            v = mn_a + q.astype(np.float64) * (sc_a / 65535.0)
            out.append((name, q, f, mn_a, sc_a, v))
    return out


def pack_exact_u16_v2(layer, entries, sidebar_groups):
    """Pack exact pre-quantized uint16 meshes with per-mesh (mn, sc) into ha-mesh-v2 without re-quantizing."""
    u16_buf = bytearray()
    face_buf = bytearray()
    all_lo = []
    all_hi = []
    staged = []

    for name, q, f, mn_a, sc_a, v in entries:
        if len(q) == 0 or len(f) == 0 or len(q) > import_hra.MAX_VERTICES:
            raise ValueError(f'Invalid vertex/face count in {layer}/{name}')
        if int(f.max()) >= len(q) or int(f.max()) >= 65535:
            raise ValueError(f'Invalid face index in {layer}/{name}')
        all_lo.append(v.min(axis=0))
        all_hi.append(v.max(axis=0))
        v_rel = len(u16_buf)
        u16_buf.extend(q.astype('<u2').tobytes())
        f_rel = len(face_buf)
        face_buf.extend(f.astype('<u2').tobytes())
        staged.append([name, len(q), len(f), v_rel, f_rel, 'u16', mn_a.tolist(), sc_a.tolist()])

    face_base = len(u16_buf)
    meta = []
    for name, nv, nf, v_rel, f_rel, enc, mn_l, sc_l in staged:
        meta.append([name, nv, nf, v_rel, face_base + f_rel, enc, mn_l, sc_l])

    glo = np.min(all_lo, axis=0)
    ghi = np.max(all_hi, axis=0)
    gsc = float((ghi - glo).max()) or 1.0
    gen = import_hra.compute_generation_hash(layer, meta, sidebar_groups)
    return {
        'v': import_hra.FORMAT_VERSION,
        'fmt': import_hra.FORMAT_NAME,
        'endian': import_hra.ENDIANNESS,
        'gen': gen,
        'b': base64.b64encode(bytes(u16_buf) + bytes(face_buf)).decode('ascii'),
        'm': {'mn': glo.tolist(), 'sc': gsc, 'meta': meta},
    }


def load_git_vessel_pool():
    pool = {}
    for src_layer in (*VESSEL_LAYERS, 'jantung'):
        raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{GIT_BASE_COMMIT}:data/atlas_{src_layer}.json'])
        data = json.loads(raw)
        for name, q, f, mn_a, sc_a, v in decode_any_bundle(data):
            entry = (src_layer, name, q, f, mn_a, sc_a, v)
            pool.setdefault((name, len(q), len(f)), []).append(entry)
            if name in ('Splenic_artery', 'Splenic_vein'):
                pool.setdefault((name + '.l', len(q), len(f)), []).append(entry)
    return pool


def main():
    page_path = ROOT / 'index.html'
    page = page_path.read_text(encoding='utf-8')
    layers, _ = json.JSONDecoder().raw_decode(page.split('const BL = ', 1)[1])

    git_pool = load_git_vessel_pool()
    staged_bundles = {}

    # 1. Restore exact bc3f6f9 un-degraded quantization lattices for all 6 regional vessel layers
    for layer in VESSEL_LAYERS:
        cur_data = json.loads((ROOT / 'data' / f'atlas_{layer}.json').read_bytes())
        cur_meshes = decode_any_bundle(cur_data)
        restored = []
        for name, q, f, mn_a, sc_a, v in cur_meshes:
            cands = git_pool.get((name, len(q), len(f)))
            if not cands:
                raise ValueError(f'No bc3f6f9 match for {layer}/{name} ({len(q)}, {len(f)})')
            best = min(cands, key=lambda c: float(np.max(np.abs(c[6] - v))))
            diff_um = float(np.linalg.norm(best[6] - v, axis=1).max() * 1e6)
            if diff_um > 25.0:
                raise ValueError(f'Unexpected drift {diff_um:.2f}um matching {layer}/{name}')
            # Keep the working-tree mesh name (e.g. Splenic_artery.l) with bc3f6f9's un-degraded (q, f, mn, sc)
            restored.append((name, best[2], best[3], best[4], best[5], best[6]))
        bundle = pack_exact_u16_v2(layer, restored, layers[layer]['g'])
        staged_bundles[layer] = bundle
        layers[layer]['gen'] = bundle['gen']

    # 2. Losslessly wrap the other 7 legacy bundles in ha-mesh-v2 preserving exact bit-for-bit u16 coordinates
    for layer in OTHER_LEGACY_LAYERS:
        cur_data = json.loads((ROOT / 'data' / f'atlas_{layer}.json').read_bytes())
        cur_meshes = decode_any_bundle(cur_data)
        bundle = pack_exact_u16_v2(layer, cur_meshes, layers[layer]['g'])
        staged_bundles[layer] = bundle
        layers[layer]['gen'] = bundle['gen']

    updated_page = import_hra.replace_page_data(page, 'BL', layers)
    for layer, bundle in staged_bundles.items():
        import_hra.write_data(ROOT / 'data' / f'atlas_{layer}.json', bundle)
    import_hra.write_data_atomic(page_path, updated_page)

    for layer, bundle in staged_bundles.items():
        print(f'{layer:12s}: gen={bundle["gen"]} meshes={len(bundle["m"]["meta"]):3d} (v2 exact u16)')


if __name__ == '__main__':
    main()
