"""Convert the pinned HuBMAP reference meshes to the atlas's packed format."""

import argparse
import base64
import json
from pathlib import Path
import re
import struct

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MAX_VERTICES = 65536
SIDES = {'': 'garis tengah', 'l': 'kiri', 'r': 'kanan', 'lr': 'kanan & kiri'}


def mesh_item(name, label, latin, detail, *parts):
    return name, label, latin, detail, parts


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


def read_glb(path):
    blob = path.read_bytes()
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
    for start in range(0, len(faces), MAX_VERTICES // 3):
        chunk = faces[start:start + MAX_VERTICES // 3]
        used, indices = np.unique(chunk, return_inverse=True)
        yield vertices[used], indices.reshape(-1, 3)


def pack(meshes):
    lo = np.min([vertices.min(axis=0) for _, vertices, _ in meshes], axis=0)
    hi = np.max([vertices.max(axis=0) for _, vertices, _ in meshes], axis=0)
    scale = float((hi - lo).max())
    vertex_buffer, face_buffer = bytearray(), bytearray()
    metadata = []
    for name, vertices, faces in meshes:
        if len(vertices) > MAX_VERTICES or faces.max() >= len(vertices):
            raise ValueError(f'Invalid indices for {name}')
        quantized = np.rint((vertices - lo) * (65535 / scale)).astype('<u2')
        metadata.append([name, len(vertices), len(faces), len(vertex_buffer) // 2, len(face_buffer) // 2])
        vertex_buffer.extend(quantized.tobytes())
        face_buffer.extend(faces.astype('<u2').tobytes())
    for row in metadata:
        row[4] += len(vertex_buffer) // 2
    return {
        'b': base64.b64encode(vertex_buffer + face_buffer).decode('ascii'),
        'm': {'mn': lo.tolist(), 'sc': scale, 'meta': metadata},
    }


def write_data(path, data):
    path.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')


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


def build_layer(model_files, groups, source_dir):
    models = {}
    for key, (release, file) in model_files.items():
        folder = 'v11' if release == 'v1.1' else 'v12'
        models[key] = read_glb(source_dir / folder / (file + '.glb'))

    meshes, sidebar = [], []
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
                        for chunk in mesh_chunks(vertices, faces):
                            slots.append(len(meshes))
                            meshes.append((mesh_name, *chunk))
            item = {'id': name, 'n': label, 'l': latin, 'e': name.replace('_', ' '),
                    'r': group, 's': SIDES[''.join(sorted(sides))], 'p': slots}
            if detail:
                item['d'] = detail
            entries.append(item)
        sidebar.append({'g': group, 'items': entries})
    return pack(meshes), {'reference': True, 'g': sidebar}


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
    args = parser.parse_args()

    page_path = ROOT / 'index.html'
    page = page_path.read_text(encoding='utf-8')
    layers, _ = json.JSONDecoder().raw_decode(page.split('const BL = ', 1)[1])
    for layer, (model_files, groups) in REFERENCES.items():
        data, layers[layer] = build_layer(model_files, groups, args.source_dir)
        write_data(ROOT / 'data' / f'atlas_{layer}.json', data)
    page_path.write_text(replace_page_data(page, 'BL', layers), encoding='utf-8')


if __name__ == '__main__':
    main()
