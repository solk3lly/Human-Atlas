"""Convert the pinned HuBMAP reference meshes to the atlas's v2 precision-preserving format."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
# WebGL 2.0 §5.14 / glTF 2.0 #meshes-topology: uint16 index 65535 (0xFFFF) is reserved
# for PRIMITIVE_RESTART_FIXED_INDEX, so uint16-indexed chunks may have at most 65535 vertices (indices 0..65534).
MAX_VERTICES = 65535
FORMAT_VERSION = 2
FORMAT_NAME = 'ha-mesh-v2'
ENDIANNESS = 'le'
SIDES = {'': 'garis tengah', 'l': 'kiri', 'r': 'kanan', 'lr': 'kanan & kiri'}

# Adaptive precision gate thresholds (grounded in Metrics Reloaded + anatomical morphometry):
# Promote a mesh/chunk-group from per-mesh anisotropic uint16 to exact IEEE-754 float32
# if quantization introduces any new zero-area triangle, loses any valid vertex normal,
# tilts p99 vertex normals beyond 1.0 deg, or displaces any vertex by more than 5.0 um.
MAX_U16_DISP_M = 5.0e-6
MAX_U16_P99_NORMAL_DEG = 1.0

# Pinned SHA-256 digests for HuBMAP ccf-releases commit b036a91aaf7234f462b1249d4a5f4fb0e982f412
PINNED_COMMIT = 'b036a91aaf7234f462b1249d4a5f4fb0e982f412'
PINNED_SHA256 = {
    ('v1.1', 'VH_M_Heart'): 'aa56c04740e7bd5b0195fe25042d614ede965f04a569cfced689f574d4f6a74c',
    ('v1.2', 'VH_M_Kidney_L'): '733eef9ec169796196470e538dc248c4397bce0ff7ed679f7b7eb0bb9f185612',
    ('v1.2', 'VH_M_Kidney_R'): 'ff9821e0b8fb7fa6174a07b9cafb9f98bb25feca34ddc0e802beeefb24cd3779',
    ('v1.2', 'VH_M_Ureter_L'): 'b6e27766b5e5663fe31d96052caa49cd4fab782eed39367c26fec517b3ba0ebb',
    ('v1.2', 'VH_M_Ureter_R'): 'be2d0331aed637f2f291a342ee760dda41d3418a9e2e9a4070e1e845e3b3e581',
    ('v1.2', 'VH_M_Urethra'): '5cd26495cb6c674e04393ea3ed467c0ab29af870a591623f822b7e0adde4d62d',
    ('v1.2', 'VH_M_Urinary_Bladder'): '43b7f17e3f498d5e494a7757ce86c183ae458f83724ceaf922f6bdd6a35ff339',
    ('v1.2', 'VH_M_Spleen'): '572ca93068f6e7506d5653ca16292ec3048ad52957d34f389cb67c8961a7c8fb',
    ('v1.2', 'VH_M_Thymus'): 'fd048515346fce788ade60c618743c875d26dd837815ab83f555c1ee2ff0a10d',
    ('v1.2', 'NIH_M_Lymph_Node'): '7b047002cbb1dc06f37baa441783390d76cdb444b6144d6caa623923707953fd',
    ('v1.2', 'VH_M_Small_Intestine'): 'e9d05a22c0132d375f8c242ad491ea68365681904cb391e648187de5247b4570',
    ('v1.2', 'SBU_M_Intestine_Large'): '84a66fb4e2dd07dffc284435da896284c3bddc5b6eb6f8e2f8c1b9130387b66b',
}


def mesh_item(name, label, latin, detail, *parts):
    return name, label, latin, detail, parts


def compute_generation_hash(layer, meta, sidebar_groups):
    payload = {
        'layer': layer,
        'meta': [[row[0], row[1], row[2]] for row in meta],
        'items': [[item['id'], item['p']] for group in sidebar_groups for item in group['items']],
    }
    raw = json.dumps(payload, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:16]


def node_transform(node):
    if 'matrix' in node:
        return np.asarray(node['matrix']).reshape(4, 4).T

    x, y, z, w = node.get('rotation', (0, 0, 0, 1))
    rotation = np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ])
    transform = np.eye(4)
    transform[:3, :3] = rotation * node.get('scale', (1, 1, 1))
    transform[:3, 3] = node.get('translation', (0, 0, 0))
    return transform


def read_glb(path, expected_sha256=None):
    blob = path.read_bytes()
    if expected_sha256 is not None:
        actual = hashlib.sha256(blob).hexdigest()
        if actual != expected_sha256:
            raise ValueError(f'SHA-256 mismatch for {path}: got {actual}, expected {expected_sha256}')
    magic, version, size = struct.unpack_from('<4sII', blob)
    json_size, json_type = struct.unpack_from('<I4s', blob, 12)
    bin_size, bin_type = struct.unpack_from('<I4s', blob, 20 + json_size)
    if (magic, version, size, json_type, bin_type) != (b'glTF', 2, len(blob), b'JSON', b'BIN\x00'):
        raise ValueError(f'Unsupported GLB: {path}')
    model = json.loads(blob[20:20 + json_size])
    buf = memoryview(blob)[28 + json_size:28 + json_size + bin_size]

    def accessor(index, width, data_type):
        spec = model['accessors'][index]
        view = model['bufferViews'][spec['bufferView']]
        if spec.get('sparse') or spec.get('normalized') or view['buffer'] != 0:
            raise ValueError(f'Unsupported accessor: {path}, {index}')
        offset = view.get('byteOffset', 0) + spec.get('byteOffset', 0)
        stride = view.get('byteStride', width * data_type.itemsize)
        return np.ndarray((spec['count'], width), dtype=data_type, buffer=buf,
                          offset=offset, strides=(stride, data_type.itemsize))

    def visit(index, transform):
        node = model['nodes'][index]
        world = transform @ node_transform(node)
        if 'mesh' in node:
            parts = []
            for primitive in model['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode', 4) != 4:
                    raise ValueError(f'Expected triangles: {path}, {node["name"]}')
                index_id = primitive['indices']
                index_kind = model['accessors'][index_id]['componentType']
                index_type = np.dtype({5121: 'u1', 5123: '<u2', 5125: '<u4'}[index_kind])
                vertices = accessor(primitive['attributes']['POSITION'], 3, np.dtype('<f4'))
                vertices = vertices @ world[:3, :3].T + world[:3, 3]
                faces = accessor(index_id, 1, index_type).reshape(-1, 3)
                if np.linalg.det(world[:3, :3]) < 0:
                    faces = faces[:, ::-1]
                parts.append((vertices, faces))
            yield node['name'], parts
        for child in node.get('children', ()):
            yield from visit(child, world)

    return dict(result for root in model['scenes'][model.get('scene', 0)]['nodes']
                for result in visit(root, np.eye(4)))


def mesh_chunks(vertices, faces):
    if len(vertices) <= MAX_VERTICES:
        yield vertices, faces
        return
    step = MAX_VERTICES // 3
    for start in range(0, len(faces), step):
        chunk = faces[start:start + step]
        used, indices = np.unique(chunk, return_inverse=True)
        yield vertices[used], indices.reshape(-1, 3)


def _zero_area_mask(verts, faces):
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return np.all(cross == 0.0, axis=1)


def _vertex_normals(verts, faces):
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    vn = np.zeros_like(verts, dtype=np.float64)
    np.add.at(vn, faces[:, 0], fn)
    np.add.at(vn, faces[:, 1], fn)
    np.add.at(vn, faces[:, 2], fn)
    norms = np.linalg.norm(vn, axis=1, keepdims=True)
    ok = norms[:, 0] > 0.0
    vn[ok] /= norms[ok]
    return vn, ok


def _evaluate_u16_group(group_meshes, lo, sc):
    """Evaluate per-group local anisotropic uint16 quantization against float32 source."""
    sc_safe = np.where(sc > 0.0, sc, 1.0)
    max_disp = 0.0
    new_zero = 0
    lost_normals = 0
    max_p99_deg = 0.0
    for vertices, faces in group_meshes:
        v64 = np.asarray(vertices, dtype=np.float64)
        f64 = np.asarray(faces, dtype=np.int64)
        q = np.rint((v64 - lo) * (65535.0 / sc_safe)).astype('<u2')
        rec = lo + q.astype(np.float64) * (sc_safe / 65535.0)
        disp = float(np.linalg.norm(rec - v64, axis=1).max())
        if disp > max_disp:
            max_disp = disp
        sz = _zero_area_mask(v64, f64)
        ez = _zero_area_mask(rec, f64)
        new_zero += int(np.sum(ez & ~sz))
        ns, oks = _vertex_normals(v64, f64)
        na, oka = _vertex_normals(rec, f64)
        lost_normals += int(np.sum(oks & ~oka))
        both = oks & oka
        if np.any(both):
            dots = np.clip(np.sum(ns[both] * na[both], axis=1), -1.0, 1.0)
            p99 = float(np.percentile(np.degrees(np.arccos(dots)), 99))
            if p99 > max_p99_deg:
                max_p99_deg = p99
    return {
        'max_disp': max_disp,
        'new_zero': new_zero,
        'lost_normals': lost_normals,
        'p99_normal_deg': max_p99_deg,
    }


def _needs_f32(metrics):
    return (
        metrics['new_zero'] > 0
        or metrics['lost_normals'] > 0
        or metrics['max_disp'] > MAX_U16_DISP_M
        or metrics['p99_normal_deg'] > MAX_U16_P99_NORMAL_DEG
    )


def pack(meshes, layer=None, sidebar_groups=None):
    """Pack meshes into ha-mesh-v2 with per-group anisotropic u16 + selective f32.

    Each entry in `meshes` may be `(name, vertices, faces)` or `(name, vertices, faces, seam_group)`.
    Chunks sharing the same `seam_group` receive identical quantization bounds and encoding to
    guarantee crack-free boundaries across split meshes.
    """
    if not meshes:
        raise ValueError('Cannot pack empty mesh list')

    normalized = []
    for idx, entry in enumerate(meshes):
        if len(entry) == 3:
            name, vertices, faces = entry
            seam_group = idx
        else:
            name, vertices, faces, seam_group = entry
        v64 = np.asarray(vertices, dtype=np.float64)
        f64 = np.asarray(faces, dtype=np.int64)
        if len(v64) == 0 or len(f64) == 0:
            raise ValueError(f'Empty geometry for {name}')
        if len(v64) > MAX_VERTICES:
            raise ValueError(f'Mesh {name} has {len(v64)} vertices > MAX_VERTICES ({MAX_VERTICES})')
        if f64.min() < 0 or f64.max() >= len(v64) or f64.max() >= 65535:
            raise ValueError(f'Invalid face indices for {name}: range [{f64.min()}, {f64.max()}], nv={len(v64)}')
        if not np.all(np.isfinite(v64)):
            raise ValueError(f'Non-finite vertex coordinates in {name}')
        normalized.append((name, v64, f64, seam_group))

    # Layer-wide bounds (informational envelope)
    glo = np.min([v.min(axis=0) for _, v, _, _ in normalized], axis=0)
    ghi = np.max([v.max(axis=0) for _, v, _, _ in normalized], axis=0)
    gscale = float((ghi - glo).max())
    if not np.isfinite(gscale) or gscale <= 0.0:
        gscale = 1.0

    # Group by seam_group so split chunks share identical quantization lattice & encoding
    group_indices = {}
    for idx, (_, _, _, sg) in enumerate(normalized):
        group_indices.setdefault(sg, []).append(idx)

    group_params = {}
    for sg, idxs in group_indices.items():
        grp_meshes = [(normalized[i][1], normalized[i][2]) for i in idxs]
        lo = np.min([v.min(axis=0) for v, _ in grp_meshes], axis=0)
        hi = np.max([v.max(axis=0) for v, _ in grp_meshes], axis=0)
        span = hi - lo
        sc_safe = np.where(span > 0.0, span, 1.0)
        metrics = _evaluate_u16_group(grp_meshes, lo, sc_safe)
        enc = 'f32' if _needs_f32(metrics) else 'u16'
        group_params[sg] = (enc, lo, sc_safe)

    # Pack contiguous aligned blocks: [all f32 vertices][all u16 vertices][all u16 faces]
    f32_buf = bytearray()
    u16_buf = bytearray()
    face_buf = bytearray()
    staged_meta = []

    for name, v64, f64, sg in normalized:
        enc, lo, sc_safe = group_params[sg]
        if enc == 'f32':
            v_rel = len(f32_buf)
            f32_buf.extend(v64.astype('<f4').tobytes())
        else:
            v_rel = len(u16_buf)
            q = np.rint((v64 - lo) * (65535.0 / sc_safe)).astype('<u2')
            u16_buf.extend(q.tobytes())
        f_rel = len(face_buf)
        face_buf.extend(f64.astype('<u2').tobytes())
        staged_meta.append([name, len(v64), len(f64), v_rel, f_rel, enc, lo.tolist(), sc_safe.tolist()])

    u16_base = len(f32_buf)
    face_base = u16_base + len(u16_buf)
    metadata = []
    for name, nv, nf, v_rel, f_rel, enc, lo_list, sc_list in staged_meta:
        v_off = v_rel if enc == 'f32' else u16_base + v_rel
        f_off = face_base + f_rel
        metadata.append([name, nv, nf, v_off, f_off, enc, lo_list, sc_list])

    raw_bytes = bytes(f32_buf) + bytes(u16_buf) + bytes(face_buf)
    bundle = {
        'v': FORMAT_VERSION,
        'fmt': FORMAT_NAME,
        'endian': ENDIANNESS,
        'b': base64.b64encode(raw_bytes).decode('ascii'),
        'm': {'mn': glo.tolist(), 'sc': gscale, 'meta': metadata},
    }
    if layer is not None and sidebar_groups is not None:
        bundle['gen'] = compute_generation_hash(layer, metadata, sidebar_groups)
    return bundle


def write_data_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_data(path, data):
    write_data_atomic(path, json.dumps(data, separators=(',', ':')))


def replace_page_data(page, name, data):
    prefix = f'const {name} = '
    start = page.index(prefix) + len(prefix)
    _, length = json.JSONDecoder().raw_decode(page[start:])
    formatted = json.dumps(data, ensure_ascii=False)
    # Match the spacing used in the existing inline JSON, including nested objects.
    formatted = re.sub(r'"(?:[^"\\]|\\.)*"|[{}]', lambda m: (
        '{ ' if m[0] == '{' else ' }' if m[0] == '}' else m[0]
    ), formatted)
    return page[:start] + formatted + page[start + length:]


def build_layer(layer_key, model_files, groups, source_dir, verify_checksums=True):
    models = {}
    for key, (release, file) in model_files.items():
        folder = 'v11' if release == 'v1.1' else 'v12'
        expected = PINNED_SHA256.get((release, file)) if verify_checksums else None
        models[key] = read_glb(source_dir / folder / (file + '.glb'), expected_sha256=expected)

    meshes, sidebar = [], []
    seam_counter = 0
    for group, definitions in groups:
        entries = []
        for name, label, latin, detail, parts in definitions:
            slots, sides = [], set()
            for model, pattern, side in parts:
                matching = [node for node in models[model] if re.fullmatch(pattern, node)]
                if not matching:
                    raise ValueError(f'{model} has no node matching {pattern}')
                if side:
                    sides.add(side)
                mesh_name = f'{name}.{side}' if side else name
                for node in matching:
                    for vertices, faces in models[model].pop(node):
                        seam_id = seam_counter
                        seam_counter += 1
                        for chunk_v, chunk_f in mesh_chunks(vertices, faces):
                            slots.append(len(meshes))
                            meshes.append((mesh_name, chunk_v, chunk_f, seam_id))
            item = {'id': name, 'n': label, 'l': latin, 'e': name.replace('_', ' '),
                    'r': group, 's': SIDES[''.join(sorted(sides))], 'p': slots}
            if detail:
                item['d'] = detail
            entries.append(item)
        sidebar.append({'g': group, 'items': entries})
    bundle = pack(meshes, layer=layer_key, sidebar_groups=sidebar)
    return bundle, {'reference': True, 'gen': bundle['gen'], 'g': sidebar}


def heart_mesh(name, label, latin, detail, pattern, side=''):
    return mesh_item(name, label, latin, detail, ('heart', 'VH_M_' + pattern, side))


HEART = [
    ('Ruang dan Septum Jantung', [
        heart_mesh('Right_atrium', 'Atrium Kanan', 'Atrium dextrum', 'atrium_r', 'right_cardiac_atrium', 'r'),
        heart_mesh('Left_atrium', 'Atrium Kiri', 'Atrium sinistrum', 'atrium_l', 'left_cardiac_atrium', 'l'),
        heart_mesh('Right_ventricle', 'Ventrikel Kanan', 'Ventriculus dexter', 'ventricle_r', 'heart_right_ventricle', 'r'),
        heart_mesh('Left_ventricle', 'Ventrikel Kiri', 'Ventriculus sinister', 'ventricle_l', 'heart_left_ventricle', 'l'),
        heart_mesh('Interventricular_septum', 'Septum Interventrikular', 'Septum interventriculare',
                   'ventricular_septum', 'interventricular_septum'),
    ]),
    ('Katup dan Otot Papilaris', [
        heart_mesh('Mitral_valve', 'Katup Mitral', 'Valva mitralis', 'mitral', 'mitral_valve'),
        heart_mesh('Tricuspid_valve', 'Katup Trikuspid', 'Valva tricuspidalis', 'tricuspid', 'tricuspid_valve'),
        heart_mesh('Aortic_valve', 'Katup Aorta', 'Valva aortae', 'aortic_valve', 'aortic_valve'),
        heart_mesh('Pulmonary_valve', 'Katup Pulmonal', 'Valva trunci pulmonalis', 'pulm_valve', 'pulmonary_valve'),
        *[heart_mesh(f'Papillary_muscle_{part}', f'Otot Papilaris {label}', '', 'papillary',
                     f'papillary_muscle_of_heart_{part}', side)
          for part, label, side in [
              ('anterior', 'Anterior (Ventrikel Kanan)', 'r'),
              ('posterior', 'Posterior (Ventrikel Kanan)', 'r'),
              ('medial', 'Medial (Ventrikel Kanan)', 'r'),
              ('anterolateral', 'Anterolateral (Ventrikel Kiri)', 'l'),
              ('posteromedial', 'Posteromedial (Ventrikel Kiri)', 'l'),
          ]],
    ]),
    ('Pembuluh Koroner', [
        heart_mesh('Right_coronary_artery', 'Arteri Koroner Kanan', 'Arteria coronaria dextra', 'rca', 'right_coronary_artery', 'r'),
        heart_mesh('Left_coronary_artery', 'Arteri Koroner Kiri', 'Arteria coronaria sinistra', 'lca', 'left_coronary_artery', 'l'),
        heart_mesh('Anterior_interventricular_artery', 'Arteri Interventrikular Anterior (LAD)', 'Ramus interventricularis anterior',
                   'lad', 'left_anterior_descending_artery'),
        heart_mesh('Posterior_interventricular_artery', 'Arteri Interventrikular Posterior (PDA)', 'Ramus interventricularis posterior',
                   '', 'right_posterior_descending_artery'),
        heart_mesh('Right_marginal_artery', 'Arteri Marginal Kanan', 'Ramus marginalis dexter', '', 'right_marginal_artery', 'r'),
        heart_mesh('Left_marginal_artery', 'Arteri Marginal Kiri', 'Ramus marginalis sinister', '', 'left_marginal_branch', 'l'),
        heart_mesh('Diagonal_branches_of_lad_artery', 'Cabang Diagonal LAD', '', '',
                   'diagonal_branch_of_(?:anterior_descending_branch_of_left_coronary_artery|left_anterior_descending_artery)'),
        heart_mesh('Coronary_sinus', 'Sinus Koronarius', 'Sinus coronarius', 'coronary_sinus', 'coronary_sinus'),
        heart_mesh('Great_cardiac_vein', 'Vena Jantung Besar', 'Vena cardiaca magna', 'great_cardiac', 'great_cardiac_vein'),
        heart_mesh('Middle_cardiac_vein', 'Vena Jantung Tengah', 'Vena cardiaca media', 'middle_cardiac', 'middle_cardiac_vein'),
        heart_mesh('Small_cardiac_vein', 'Vena Jantung Kecil', 'Vena cardiaca parva', '', 'small_cardiac_vein'),
        heart_mesh('Anterior_cardiac_vein', 'Vena Jantung Anterior', 'Vena cardiaca anterior', '', 'anterior_cardiac_vein'),
        heart_mesh('Oblique_vein_of_left_atrium', 'Vena Oblik Atrium Kiri', 'Vena obliqua atrii sinistri',
                   '', 'oblique_vein_of_left_atrium', 'l'),
        heart_mesh('Posterior_vein_of_left_ventricle', 'Vena Posterior Ventrikel Kiri', '',
                   '', 'posterior_vein_of_left_ventricle', 'l'),
    ]),
    ('Sirkulasi Paru', [
        heart_mesh('Pulmonary_trunk', 'Trunkus Pulmonalis', 'Truncus pulmonalis', 'pulm_trunk', 'pulmonary_trunk'),
        *[heart_mesh(f'Pulmonary_artery_{side}', f'Arteri Pulmonalis {label}', '', 'pulm_artery',
                     f'pulmonary_artery_{side.upper()}', side)
          for side, label in [('r', 'Kanan'), ('l', 'Kiri')]],
        *[heart_mesh(f'Pulmonary_vein_{level}_{side}', f'Vena Pulmonalis {label} {side_label}', '', 'pulm_vein',
                     f'pulmonary_vein_{side.upper()}_{suffix}', side)
          for level, label, suffix in [('superior', 'Superior', 'sup'), ('inferior', 'Inferior', 'inf')]
          for side, side_label in [('r', 'Kanan'), ('l', 'Kiri')]],
    ]),
    ('Aorta dan Cabang Besar', [
        heart_mesh('Ascending_aorta', 'Aorta Asendens', 'Aorta ascendens', 'aorta_asc', 'ascending_aorta'),
        heart_mesh('Aortic_arch', 'Arkus Aorta', 'Arcus aortae', 'aortic_arch', 'aortic_arch'),
        heart_mesh('Descending_aorta', 'Aorta Desendens', 'Aorta descendens', '', 'descending_aorta_[ab]'),
        heart_mesh('Brachiocephalic_trunk', 'Trunkus Brakiosefalika', 'Truncus brachiocephalicus',
                   'brachiocephalic', 'brachiocephalic_artery_[ab]'),
        heart_mesh('Left_common_carotid_artery', 'Arteri Karotis Komunis Kiri', 'Arteria carotis communis sinistra',
                   'carotid', 'left_common_carotid_artery_[ab]', 'l'),
        heart_mesh('Left_subclavian_artery', 'Arteri Subklavia Kiri', 'Arteria subclavia sinistra',
                   'subclavian_a', 'left_subclavian_artery_[ab]', 'l'),
    ]),
    ('Vena Besar', [
        heart_mesh('Superior_vena_cava', 'Vena Kava Superior', 'Vena cava superior', 'svc', 'superior_vena_cava'),
        heart_mesh('Inferior_vena_cava', 'Vena Kava Inferior', 'Vena cava inferior', 'ivc', 'inferior_vena_cava_[ab]'),
        *[heart_mesh(f'Brachiocephalic_vein_{side}', f'Vena Brakiosefalika {label}', '', 'v_brachioceph',
                     f'brachiocephalic_vein_{side.upper()}', side)
          for side, label in [('r', 'Kanan'), ('l', 'Kiri')]],
    ]),
]


def pair(name, label, latin, detail, source, pattern):
    parts = [(f'{source}_{side}', f'VH_M_{pattern.format(side=side.upper())}', side)
             for side in ('l', 'r')]
    return mesh_item(name, label, latin, detail, *parts)


URINARY = [
    ('Ginjal', [
        pair('Kidney', 'Ginjal (Kapsul)', 'Capsula renis', 'kidney', 'kidney', 'kidney_capsule_{side}'),
        pair('Renal_cortex', 'Korteks Ginjal', 'Cortex renis', 'renal_cortex', 'kidney', 'outer_cortex_of_kidney_{side}'),
        pair('Renal_column', 'Kolumna Ginjal', 'Columna renalis', '', 'kidney', 'renal_column_{side}'),
        pair('Renal_papilla', 'Papila Ginjal', 'Papilla renalis', 'renal_papilla', 'kidney', 'renal_papilla_{side}_[a-j]'),
        mesh_item('Renal_pyramid', 'Piramida Ginjal', 'Pyramis renalis', 'renal_pyramid',
                  ('kidney_l', 'VH_M_renal_pyramid_L_[a-i]', 'l'), ('kidney_r', 'VH_M_renal_pyramid_[a-j]', 'r')),
        pair('Renal_pelvis', 'Pelvis Renalis', 'Pelvis renalis', 'renal_pelvis', 'ureter', 'renal_pelvis_{side}'),
        pair('Major_renal_calyx', 'Kaliks Mayor', 'Calix renalis major', 'calyx_major', 'ureter', 'major_calyx_{side}_[a-j]'),
        pair('Minor_renal_calyx', 'Kaliks Minor', 'Calix renalis minor', 'calyx_minor', 'ureter', 'minor_calyx_{side}_[a-j]'),
    ]),
    ('Saluran Kemih', [
        pair('Ureter', 'Ureter', 'Ureter', 'ureter', 'ureter', 'ureter_{side}'),
        mesh_item('Urinary_bladder', 'Kandung Kemih', 'Vesica urinaria', 'bladder',
                  ('bladder', 'VH_M_(?:fundus_of_urinary_bladder_(?:dome|base1)|urinary_bladder_neck_smooth_muscle)', '')),
        mesh_item('Bladder_trigone', 'Trigonum Kandung Kemih', 'Trigonum vesicae', '',
                  ('bladder', 'VH_M_trigone_of_urinary_bladder', '')),
        mesh_item('Ureteral_orifice', 'Muara Ureter', 'Ostium ureteris', '',
                  ('bladder', 'VH_M_ureteral_orifice_L', 'l'), ('bladder', 'VH_M_ureteral_orifice_R', 'r')),
        mesh_item('Prostatic_urethra', 'Uretra Prostatika', 'Pars prostatica urethrae', '',
                  ('urethra', 'VH_M_prostatic_urethra', '')),
        mesh_item('Remaining_urethra', 'Kelanjutan Uretra Pria', '', '',
                  ('urethra', 'VH_M_other_urethra', '')),
    ]),
]

LYMPH = [('Organ Limfoid', [
    mesh_item('Spleen', 'Limpa', 'Splen', 'spleen',
              ('spleen', 'VH_M_(?:(?:colic|diaphragmatic|gastric|renal)_surface_of_spleen|hilum_of_spleen)', 'l')),
    mesh_item('Thymus', 'Timus', 'Thymus', 'thymus', ('thymus', 'VH_M_thymus_lobe_[LR]', '')),
])]

LYMPH_NODE = [('Bagian Nodus Limfatikus', [
    mesh_item(name, label, latin, detail, ('node', f'Yao_{node}', ''))
    for name, label, latin, detail, node in [
        ('Lymph_node_capsule', 'Kapsul Nodus', 'Capsula nodi lymphoidei', 'node_capsule', 'capsule_of_lymph_node'),
        ('Afferent_lymphatic_vessels', 'Pembuluh Limfe Aferen', 'Vasa lymphatica afferentia', 'node_afferent', 'afferent_lymphatic_vessel'),
        ('Efferent_lymphatic_vessels', 'Pembuluh Limfe Eferen', 'Vasa lymphatica efferentia', 'node_efferent', 'efferent_lymph_node'),
        ('Lymph_node_follicles', 'Folikel Limfoid', '', '', 'follicles'),
        ('Lymph_node_paracortex', 'Parakorteks', '', '', 'paracortex'),
        ('Lymph_node_medulla', 'Medula Nodus', '', '', 'medulla_of_lymph_node'),
        ('Lymph_node_blood_vasculature', 'Pembuluh Darah Nodus', '', '', 'blood_vasculature'),
    ]
])]

SMALL_BOWEL = [('Bagian Usus Halus', [
    mesh_item('Duodenum', 'Duodenum', 'Duodenum', 'duodenum',
              ('bowel', 'VH_M_duodenum_(?:superior|descending|horizonal|ascending)', '')),
    mesh_item('Jejunum', 'Jejunum', 'Jejunum', 'jejunum_hra', ('bowel', 'VH_M_jejunum', '')),
    mesh_item('Ileum', 'Ileum', 'Ileum', 'ileum', ('bowel', 'VH_M_ileum', '')),
    mesh_item('Terminal_ileum', 'Ileum Terminal', 'Ileum terminale', 'terminal_ileum', ('bowel', 'VH_M_ileum_terminal', '')),
])]

LARGE_BOWEL = [('Bagian Usus Besar', [
    mesh_item(name, label, latin, detail, ('bowel', f'VH_M_{node}', side))
    for name, label, latin, detail, node, side in [
        ('Cecum', 'Sekum', 'Caecum', 'cecum', 'caecum', 'r'),
        ('Ileocecal_valve', 'Katup Ileosekal', 'Valva ileocaecalis', 'ileocecal_valve', 'ileocecal_valve', 'r'),
        ('Vermiform_appendix', 'Apendiks Vermiformis', 'Appendix vermiformis', 'appendix', 'vermiform_appendix', 'r'),
        ('Ascending_colon', 'Kolon Asendens', 'Colon ascendens', 'colon_asc', 'ascending_colon', 'r'),
        ('Hepatic_flexure_of_colon', 'Fleksura Hepatika', 'Flexura coli dextra', '', 'hepatic_flexure_of_colon', 'r'),
        ('Transverse_colon', 'Kolon Transversum', 'Colon transversum', 'colon_trans', 'transverse_colon', ''),
        ('Splenic_flexure_of_colon', 'Fleksura Splenika', 'Flexura coli sinistra', '', 'splenic_flexure_of_colon', 'l'),
        ('Descending_colon', 'Kolon Desendens', 'Colon descendens', 'colon_desc', 'descending_colon', 'l'),
        ('Sigmoid_colon', 'Kolon Sigmoid', 'Colon sigmoideum', 'colon_sig', 'sigmoid_colon', ''),
        ('Rectum', 'Rektum', 'Rectum', 'rectum', 'rectum', ''),
    ]
])]

REFERENCES = {
    'jantung': ({'heart': ('v1.1', 'VH_M_Heart')}, HEART),
    'urin': ({
        'kidney_l': ('v1.2', 'VH_M_Kidney_L'), 'kidney_r': ('v1.2', 'VH_M_Kidney_R'),
        'ureter_l': ('v1.2', 'VH_M_Ureter_L'), 'ureter_r': ('v1.2', 'VH_M_Ureter_R'),
        'urethra': ('v1.2', 'VH_M_Urethra'), 'bladder': ('v1.2', 'VH_M_Urinary_Bladder'),
    }, URINARY),
    'limfa': ({'spleen': ('v1.2', 'VH_M_Spleen'), 'thymus': ('v1.2', 'VH_M_Thymus')}, LYMPH),
    'limfonodus': ({'node': ('v1.2', 'NIH_M_Lymph_Node')}, LYMPH_NODE),
    'ususHalus': ({'bowel': ('v1.2', 'VH_M_Small_Intestine')}, SMALL_BOWEL),
    'ususBesar': ({'bowel': ('v1.2', 'SBU_M_Intestine_Large')}, LARGE_BOWEL),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path, help='Directory containing the pinned GLB files in v11/ and v12/')
    parser.add_argument('--skip-checksums', action='store_true', help='Skip pinned SHA-256 verification (not recommended)')
    args = parser.parse_args()

    page_path = ROOT / 'index.html'
    page = page_path.read_text(encoding='utf-8')
    layers, _ = json.JSONDecoder().raw_decode(page.split('const BL = ', 1)[1])

    # Build and validate ALL layers in memory before writing anything to disk
    staged = {}
    for layer, (model_files, groups) in REFERENCES.items():
        data, layer_cfg = build_layer(
            layer, model_files, groups, args.source_dir, verify_checksums=not args.skip_checksums)
        staged[layer] = (data, layer_cfg)
        layers[layer] = layer_cfg

    updated_page = replace_page_data(page, 'BL', layers)
    for layer, (data, _) in staged.items():
        write_data(ROOT / 'data' / f'atlas_{layer}.json', data)
    write_data_atomic(page_path, updated_page)

    for layer, (data, _) in staged.items():
        meta = data['m']['meta']
        f32_names = [row[0] for row in meta if row[5] == 'f32']
        print(f'{layer:12s}: gen={data["gen"]} meshes={len(meta):2d} f32={len(f32_names)} {f32_names}')


if __name__ == '__main__':
    main()
