"""Reconstruct the testis label from the published VOXEL-MAN SIO archive."""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

import numpy as np
from PIL import Image

import import_hra


TESTIS_LABEL = 7502
SLICE_COUNT = 774
VOXEL_COUNT = 16865
LABEL_SHA256 = '0cf4d8bd512e746f4cbe9b33c5de1d897dadc459f28e5ffdf9b4a6a6fd706196'
LAYER = 'testisRef'

# Corners are doubled to encode half-voxel offsets with integers. Each face
# lists an outward winding in the column, superior, row coordinate frame.
FACES = (
    ((-1, 0, 0), ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1))),
    ((1, 0, 0), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))),
    ((0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
    ((0, 1, 0), ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1))),
    ((0, 0, -1), ((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1))),
    ((0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
)


def read_label(archive_path):
    with zipfile.ZipFile(archive_path) as archive:
        slices = {}
        for entry in archive.namelist():
            match = re.fullmatch(r'VOXEL-MAN_segmented-internal-organs/labels/labels(\d+)\.tif', entry)
            if match:
                slices[int(match[1])] = entry
        z = sorted(slices)
        if len(z) != SLICE_COUNT or z != list(range(z[0], z[0] + SLICE_COUNT)):
            raise ValueError('Expected the 774 consecutive SIO label slices')

        selected = []
        for index in z:
            entry = slices[index]
            with Image.open(BytesIO(archive.read(entry))) as image:
                if image.size != (573, 330):
                    raise ValueError(f'Unexpected SIO image size in {entry}')
                pixels = np.argwhere(np.asarray(image) == TESTIS_LABEL)
            if pixels.size:
                selected.append(np.column_stack((np.full(len(pixels), index), pixels)))
    if sum(map(len, selected)) != VOXEL_COUNT:
        raise ValueError(f'Expected {VOXEL_COUNT} voxels for SIO label {TESTIS_LABEL}')
    label = np.vstack(selected).astype('<u2')
    if hashlib.sha256(label.tobytes()).hexdigest() != LABEL_SHA256:
        raise ValueError('SIO testis label does not match the pinned source')
    return label


def voxel_surface(samples):
    occupied = {(int(col), -int(index), int(row)) for index, row, col in samples}
    point_ids = {}
    faces = []
    for x, y, z in sorted(occupied):
        for (dx, dy, dz), corners in FACES:
            if (x + dx, y + dy, z + dz) in occupied:
                continue
            quad = []
            for a, b, c in corners:
                xyz = (2 * x + a, 2 * y + b, 2 * z + c)
                quad.append(point_ids.setdefault(xyz, len(point_ids)))
            a, b, c, d = quad
            faces.extend(((a, b, c), (a, c, d)))
    vertices = np.asarray(list(point_ids), dtype=np.float64)
    vertices = (vertices - (vertices.min(axis=0) + vertices.max(axis=0)) / 2) * .0005
    return vertices.astype(np.float32), np.asarray(faces)


def build_reference(samples):
    vertices, faces = voxel_surface(samples)
    name = 'Testis_reference'
    meshes = [(name, v, f, 0) for v, f in import_hra.mesh_chunks(vertices, faces)]
    item = {'id': name, 'n': 'Testis Spesimen Rujukan', 'l': 'Testis', 'e': 'Reference testis',
            'r': 'Visible Human Male', 's': 'garis tengah', 'd': 'testis_reference', 'p': list(range(len(meshes)))}
    groups = [{'g': 'Visible Human Male', 'items': [item]}]
    bundle = import_hra.pack(meshes, layer=LAYER, sidebar_groups=groups)
    return bundle, {'reference': True, 'source': 'sio', 'gen': bundle['gen'], 'g': groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='VOXEL-MAN_segmented-internal-organs.zip from Zenodo record 15882019')
    args = parser.parse_args()

    bundle, layer = build_reference(read_label(args.archive))
    page_path = import_hra.ROOT / 'index.html'
    page = page_path.read_text(encoding='utf-8')
    layers, _ = json.JSONDecoder().raw_decode(page.split('const BL = ', 1)[1])
    layers[LAYER] = layer
    import_hra.write_data(import_hra.ROOT / 'data' / f'atlas_{LAYER}.json', bundle)
    import_hra.write_data_atomic(page_path, import_hra.replace_page_data(page, 'BL', layers))


if __name__ == '__main__':
    main()
