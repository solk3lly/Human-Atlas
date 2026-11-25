import base64
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / 'index.html').read_text(encoding='utf-8')
LAYERS, _ = json.JSONDecoder().raw_decode(PAGE.split('const BL = ', 1)[1])


def load(layer):
    return json.loads((ROOT / 'data' / f'atlas_{layer}.json').read_bytes())


class AtlasDataTests(unittest.TestCase):
    def test_each_sidebar_layer_resolves_to_meshes(self):
        for layer, config in LAYERS.items():
            with self.subTest(layer=layer):
                data = load(layer)
                meshes = data['m']['meta']
                owned = sorted(i for group in config['g'] for item in group['items'] for i in item['p'])
                self.assertEqual(owned, list(range(len(meshes))))
                words = memoryview(base64.b64decode(data['b'], validate=True)).cast('H')
                vertex_end = 0
                face_end = sum(3 * mesh[1] for mesh in meshes)
                for _, count, faces, vo, fo in meshes:
                    self.assertEqual((vo, fo), (vertex_end, face_end))
                    vertex_end += 3 * count
                    face_end += 3 * faces
                    self.assertLess(max(words[fo:face_end]), count)
                self.assertEqual(face_end, len(words))

    def test_layers_with_duplicate_objects_draw_each_surface_once(self):
        for layer in ('saraf', 'organ', 'cerna', 'repro'):
            with self.subTest(layer=layer):
                data = load(layer)
                blob = base64.b64decode(data['b'])
                surfaces = set()
                for _, nv, nf, vo, fo in data['m']['meta']:
                    packed = (blob[2 * vo:2 * (vo + 3 * nv)], blob[2 * fo:2 * (fo + 3 * nf)])
                    self.assertNotIn(packed, surfaces)
                    surfaces.add(packed)

    def test_reference_layers_expose_missing_structures(self):
        expected = {
            'jantung': {'Mitral_valve', 'Tricuspid_valve', 'Interventricular_septum', 'Superior_vena_cava'},
            'urin': {'Kidney', 'Ureter', 'Major_renal_calyx', 'Minor_renal_calyx', 'Urinary_bladder'},
            'limfa': {'Spleen', 'Thymus'},
            'limfonodus': {'Lymph_node_capsule', 'Afferent_lymphatic_vessels', 'Efferent_lymphatic_vessels'},
            'ususHalus': {'Ileum', 'Terminal_ileum', 'Jejunum'},
            'ususBesar': {'Cecum', 'Rectum', 'Ileocecal_valve'},
        }
        for layer, ids in expected.items():
            with self.subTest(layer=layer):
                self.assertIn('reference', LAYERS[layer])
                available = {item['id'] for group in LAYERS[layer]['g'] for item in group['items']}
                self.assertLessEqual(ids, available)

    def test_respiratory_cartilages_are_bilateral(self):
        names = {mesh[0] for mesh in load('organ')['m']['meta']}
        for name in ('Major_alar_cartilage', 'Lateral_process_of_nasal_septal_cartilage',
                     'Arytenoid_cartilage', 'Corniculate_cartilage'):
            self.assertLessEqual({f'{name}.l', f'{name}.r'}, names)

    def test_vascular_regions_and_sides_agree(self):
        for layer, expected in (
            ('vsLe', {'Brachial_artery': 'kanan & kiri'}),
            ('vsAb', {'Anterior_branch_of_renal_artery': 'kanan & kiri', 'Splenic_artery': 'kiri'}),
            ('vsTo', {'Anterior_basal_segmental_artery_of_left_lung': 'kiri'}),
        ):
            with self.subTest(layer=layer):
                sides = {item['id']: item['s'] for group in LAYERS[layer]['g'] for item in group['items']}
                self.assertEqual({name: sides.get(name) for name in expected}, expected)


if __name__ == '__main__':
    unittest.main()
