"""Rebuild Z-Anatomy muscular layer (otot) and repair vessel layers from Startup.blend.

Reads Z-Anatomy/Startup.blend directly via Blender's self-describing SDNA schema (no Blender
binary required), extracts strictly 3D muscle bellies from collection '4: Muscular system',
fixes upstream Z-Anatomy defects (swapped Trapezius Ascending/Descending, unsuffixed left
Iliocostalis colli, missing contralateral Transverse_sinus.r & Axillary_vein.l, abdominal
arteries misplaced in vsTo, orphaned coronary fragments in vsTo), and packs into ha-mesh-v2.
"""

from __future__ import annotations

import argparse
import collections
import json
import mmap
import re
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import cls
import gen2
import import_hra
import validate_geometry as vg


_ARRAY_RE = re.compile(r'\[(\d+)\]')

NON_MUSCLE_RE = re.compile(
    r'\b(ligament|ligaments|capsule|disc|nucleus|annulus|joint|bursa|bursae|fascia|fasciae|membrane|cartilage|'
    r'tendon|tendons|tendinous|aponeurosis|aponeuroses|retinaculum|sheath|sheaths|septum|septa|raphe|'
    r'trochlea|band|tract|linea|symphysis|ring|canal|hiatus|foramen|space|fossa|arch|plate|pad|fat|pulley|'
    r'expansion|hood|hoods|vincula|mesotendineum|tarsus|sling|chiasm)\b',
    re.I,
)

# Group multi-head/multi-part bellies under their canonical anatomical muscle entry.
# Individual mesh names in atlas_otot.json meta remain intact (e.g. Long_head_of_biceps_brachii.r).
MULTI_HEAD_PARENT = {
    'Long_head_of_biceps_brachii': 'Biceps_brachii_muscle',
    'Short_head_of_biceps_brachii': 'Biceps_brachii_muscle',
    'Long_head_of_triceps_brachii': 'Triceps_brachii_muscle',
    'Lateral_head_of_triceps_brachii': 'Triceps_brachii_muscle',
    'Medial_head_of_triceps_brachii': 'Triceps_brachii_muscle',
    'Clavicular_part_of_deltoid_muscle': 'Deltoid_muscle',
    'Acromial_part_of_deltoid_muscle': 'Deltoid_muscle',
    'Scapular_spinal_part_of_deltoid_muscle': 'Deltoid_muscle',
    'Clavicular_head_of_pectoralis_major_muscle': 'Pectoralis_major_muscle',
    'Sternocostal_head_of_pectoralis_major_muscle': 'Pectoralis_major_muscle',
    '(Abdominal_part_of_pectoralis_major_muscle)': 'Pectoralis_major_muscle',
    'Long_head_of_biceps_femoris': 'Biceps_femoris_muscle',
    'Short_head_of_biceps_femoris': 'Biceps_femoris_muscle',
    'Lateral_head_of_gastrocnemius': 'Gastrocnemius_muscle',
    'Medial_head_of_gastrocnemius': 'Gastrocnemius_muscle',
    'Deep_part_of_masseter': 'Masseter',
    'Superficial_part_of_masseter': 'Masseter',
    'Inferior_head_of_lateral_pterygoid_muscle': 'Lateral_pterygoid_muscle',
    'Superior_head_of_lateral_pterygoid_muscle': 'Lateral_pterygoid_muscle',
    'Humeral_head_of_extensor_carpi_ulnaris': 'Extensor_carpi_ulnaris',
    'Ulnar_head_of_extensor_carpi_ulnaris': 'Extensor_carpi_ulnaris',
    'Humeral_head_of_flexor_carpi_ulnaris': 'Flexor_carpi_ulnaris',
    'Ulnar_head_of_flexor_carpi_ulnaris': 'Flexor_carpi_ulnaris',
    'Humero-ulnar_head_of_flexor_digitorum_superficialis': 'Flexor_digitorum_superficialis',
    'Radial_head_of_flexor_digitorum_superficialis': 'Flexor_digitorum_superficialis',
    'Deep_head_of_pronator_teres': 'Pronator_teres',
    'Superficial_head_of_pronator_teres': 'Pronator_teres',
    'Oblique_head_of_adductor_hallucis': 'Adductor_hallucis',
    'Transverse_head_of_adductor_hallucis': 'Adductor_hallucis',
    'Oblique_head_of_adductor_pollicis': 'Adductor_pollicis',
    'Transverse_head_of_adductor_pollicis': 'Adductor_pollicis',
    'Deep_head_of_flexor_pollicis_brevis': 'Flexor_pollicis_brevis',
    'Superficial_head_of_flexor_pollicis_brevis': 'Flexor_pollicis_brevis',
    'Lateral_head_of_flexor_hallucis_brevis': 'Flexor_hallucis_brevis',
    'Medial_head_of_flexor_hallucis_brevis': 'Flexor_hallucis_brevis',
    'Orbital_part_of_orbicularis_oculi': 'Orbicularis_oculi',
    'Palpebral_part_of_orbicularis_oculi': 'Orbicularis_oculi',
}


def _align4(pos: int) -> int:
    return (pos + 3) & ~3


def _field_size(name: str, type_len: int, ptr_size: int) -> int:
    is_ptr = name.startswith('*') or '(*' in name
    base = ptr_size if is_ptr else type_len
    mult = 1
    for m in _ARRAY_RE.finditer(name):
        mult *= int(m.group(1))
    return base * mult


def _clean_field_name(name: str) -> str:
    s = name.lstrip('*')
    if '[' in s:
        s = s.split('[', 1)[0]
    return s


class BlendFile:
    """Minimal self-describing Blender SDNA reader with per-ID DATA scoping."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._f = self.path.open('rb')
        self.mm = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        hdr = self.mm[:12]
        if not hdr.startswith(b'BLENDER'):
            raise ValueError(f'Expected uncompressed .blend file, got header {hdr!r}')
        self.ptr_size = 8 if hdr[7:8] == b'-' else 4
        self.endian = '<' if hdr[8:9] == b'v' else '>'
        self.version = int(hdr[9:12].decode('ascii'))
        self.ptr_fmt = f'{self.endian}{"Q" if self.ptr_size == 8 else "I"}'
        self.bhead_fmt = f'{self.endian}4si{"Q" if self.ptr_size == 8 else "I"}ii'
        self.bhead_size = struct.calcsize(self.bhead_fmt)

        self.blocks = []
        self.id_by_old = {}
        self.by_code = {}
        self._scan_blocks()
        self._parse_sdna()

    def close(self):
        self.mm.close()
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _scan_blocks(self):
        pos = 12
        n = len(self.mm)
        unpack = struct.Struct(self.bhead_fmt).unpack_from
        idx = 0
        while pos + self.bhead_size <= n:
            code, length, old, sdna_nr, count = unpack(self.mm, pos)
            data_off = pos + self.bhead_size
            blk = (code, length, old, sdna_nr, count, data_off)
            self.blocks.append(blk)
            if old and code != b'DATA':
                self.id_by_old[old] = (idx, blk)
            self.by_code.setdefault(code, []).append((idx, blk))
            idx += 1
            if code == b'ENDB':
                break
            pos = data_off + length

    def _owned_data_map(self, id_idx: int) -> dict:
        owned = {}
        n = len(self.blocks)
        j = id_idx + 1
        while j < n and self.blocks[j][0] == b'DATA':
            b = self.blocks[j]
            owned[b[2]] = b
            j += 1
        return owned

    def _parse_sdna(self):
        _, (_, length, _, _, _, off) = self.by_code[b'DNA1'][0]
        buf = self.mm[off:off + length]
        assert buf[:4] == b'SDNA'
        p = 4
        assert buf[p:p + 4] == b'NAME'; p += 4
        num_names, = struct.unpack_from(f'{self.endian}i', buf, p); p += 4
        names = []
        for _ in range(num_names):
            end = buf.index(b'\x00', p)
            names.append(buf[p:end].decode('latin1'))
            p = end + 1
        p = _align4(p)

        assert buf[p:p + 4] == b'TYPE'; p += 4
        num_types, = struct.unpack_from(f'{self.endian}i', buf, p); p += 4
        types = []
        for _ in range(num_types):
            end = buf.index(b'\x00', p)
            types.append(buf[p:end].decode('latin1'))
            p = end + 1
        p = _align4(p)

        assert buf[p:p + 4] == b'TLEN'; p += 4
        tlens = list(struct.unpack_from(f'{self.endian}{num_types}h', buf, p))
        p = _align4(p + 2 * num_types)

        assert buf[p:p + 4] == b'STRC'; p += 4
        num_structs, = struct.unpack_from(f'{self.endian}i', buf, p); p += 4

        self.struct_by_name = {}
        for s_idx in range(num_structs):
            t_idx, num_fields = struct.unpack_from(f'{self.endian}hh', buf, p); p += 4
            s_name = types[t_idx]
            s_len = tlens[t_idx]
            fields = {}
            foff = 0
            for _ in range(num_fields):
                ft_idx, fn_idx = struct.unpack_from(f'{self.endian}hh', buf, p); p += 4
                ftype = types[ft_idx]
                fname = names[fn_idx]
                fsize = _field_size(fname, tlens[ft_idx], self.ptr_size)
                fields[_clean_field_name(fname)] = (foff, ftype, fname, fsize)
                foff += fsize
            self.struct_by_name[s_name] = (s_idx, s_len, fields)

    def struct_fields(self, sname: str):
        return self.struct_by_name[sname][2]

    def struct_size(self, sname: str) -> int:
        return self.struct_by_name[sname][1]

    def read_ptr(self, base_off: int, sname: str, field: str) -> int:
        foff = self.struct_fields(sname)[field][0]
        return struct.unpack_from(self.ptr_fmt, self.mm, base_off + foff)[0]

    def read_int(self, base_off: int, sname: str, field: str) -> int:
        foff, _, _, fsize = self.struct_fields(sname)[field]
        fmt = {1: 'b', 2: 'h', 4: 'i', 8: 'q'}[fsize]
        return struct.unpack_from(f'{self.endian}{fmt}', self.mm, base_off + foff)[0]

    def read_cstr(self, base_off: int, sname: str, field: str) -> str:
        foff, _, _, fsize = self.struct_fields(sname)[field]
        raw = self.mm[base_off + foff:base_off + foff + fsize]
        z = raw.find(b'\x00')
        if z != -1:
            raw = raw[:z]
        return raw.decode('utf-8', errors='replace')

    def read_id_name(self, base_off: int, sname: str) -> str:
        id_off = self.struct_fields(sname)['id'][0]
        return self.read_cstr(base_off + id_off, 'ID', 'name')

    def read_floats(self, base_off: int, sname: str, field: str) -> np.ndarray:
        foff, _, _, fsize = self.struct_fields(sname)[field]
        return np.frombuffer(self.mm, dtype=f'{self.endian}f4', count=fsize // 4, offset=base_off + foff).copy()

    def iter_listbase(self, base_off: int, sname: str, field: str, lookup: dict):
        lb_off = self.struct_fields(sname)[field][0]
        ptr = self.read_ptr(base_off + lb_off, 'ListBase', 'first')
        seen = set()
        while ptr and ptr not in seen:
            seen.add(ptr)
            blk = lookup.get(ptr)
            if not blk:
                break
            yield blk
            ptr = struct.unpack_from(self.ptr_fmt, self.mm, blk[5])[0]

    def get_customdata_layers(self, mesh_off: int, cd_field: str, owned: dict):
        cd_off = self.struct_fields('Mesh')[cd_field][0]
        totlayer = self.read_int(mesh_off + cd_off, 'CustomData', 'totlayer')
        layers_ptr = self.read_ptr(mesh_off + cd_off, 'CustomData', 'layers')
        out = []
        if not layers_ptr or totlayer <= 0 or layers_ptr not in owned:
            return out
        blk = owned[layers_ptr]
        layer_sz = self.struct_size('CustomDataLayer')
        for i in range(totlayer):
            loff = blk[5] + i * layer_sz
            out.append((
                self.read_int(loff, 'CustomDataLayer', 'type'),
                self.read_cstr(loff, 'CustomDataLayer', 'name'),
                self.read_ptr(loff, 'CustomDataLayer', 'data'),
            ))
        return out

    def extract_mesh_local(self, mesh_entry) -> tuple[np.ndarray, np.ndarray]:
        midx, mesh_blk = mesh_entry
        moff = mesh_blk[5]
        owned = self._owned_data_map(midx)
        totvert = self.read_int(moff, 'Mesh', 'totvert')
        totpoly = self.read_int(moff, 'Mesh', 'totpoly')
        totloop = self.read_int(moff, 'Mesh', 'totloop')
        if totvert == 0 or totpoly == 0 or totloop == 0:
            return np.zeros((0, 3), dtype=np.float64), np.zeros((0, 3), dtype=np.int64)

        verts = None
        for ltype, lname, ldata in self.get_customdata_layers(moff, 'vdata', owned):
            if lname == 'position' and ldata in owned:
                verts = np.frombuffer(self.mm, dtype='<f4', count=totvert * 3, offset=owned[ldata][5]).reshape(totvert, 3).astype(np.float64)
                break
            if ltype == 0 and ldata in owned:
                mv_sz = self.struct_size('MVert')
                co_off = self.struct_fields('MVert')['co'][0]
                dt = np.dtype({'names': ['co'], 'formats': [('<f4', (3,))], 'offsets': [co_off], 'itemsize': mv_sz})
                verts = np.frombuffer(self.mm, dtype=dt, count=totvert, offset=owned[ldata][5])['co'].astype(np.float64)
                break
        if verts is None:
            raise ValueError('Missing vertex positions')

        loop_v = None
        for ltype, lname, ldata in self.get_customdata_layers(moff, 'ldata', owned):
            if lname == '.corner_vert' and ldata in owned:
                loop_v = np.frombuffer(self.mm, dtype='<i4', count=totloop, offset=owned[ldata][5]).astype(np.int64)
                break
            if ltype == 26 and ldata in owned:
                ml_sz = self.struct_size('MLoop')
                v_off = self.struct_fields('MLoop')['v'][0]
                dt = np.dtype({'names': ['v'], 'formats': ['<i4'], 'offsets': [v_off], 'itemsize': ml_sz})
                loop_v = np.frombuffer(self.mm, dtype=dt, count=totloop, offset=owned[ldata][5])['v'].astype(np.int64)
                break
        if loop_v is None:
            raise ValueError('Missing loop vertices')

        loopstart = totloop_arr = None
        for ltype, lname, ldata in self.get_customdata_layers(moff, 'pdata', owned):
            if ltype == 25 and ldata in owned:
                mp_sz = self.struct_size('MPoly')
                ls_off = self.struct_fields('MPoly')['loopstart'][0]
                tl_off = self.struct_fields('MPoly')['totloop'][0]
                dt = np.dtype({'names': ['ls', 'tl'], 'formats': ['<i4', '<i4'], 'offsets': [ls_off, tl_off], 'itemsize': mp_sz})
                parr = np.frombuffer(self.mm, dtype=dt, count=totpoly, offset=owned[ldata][5])
                loopstart, totloop_arr = parr['ls'], parr['tl']
                break
        if loopstart is None:
            raise ValueError('Missing polygons')

        parts = []
        m3 = totloop_arr == 3
        if np.any(m3):
            ls = loopstart[m3]
            parts.append(np.stack([loop_v[ls], loop_v[ls + 1], loop_v[ls + 2]], axis=1))
        m4 = totloop_arr == 4
        if np.any(m4):
            ls = loopstart[m4]
            a, b, c, d = loop_v[ls], loop_v[ls + 1], loop_v[ls + 2], loop_v[ls + 3]
            parts.append(np.stack([a, b, c], axis=1))
            parts.append(np.stack([a, c, d], axis=1))
        mn = totloop_arr > 4
        if np.any(mn):
            extra = []
            for ls_i, tl_i in zip(loopstart[mn].tolist(), totloop_arr[mn].tolist()):
                v0 = loop_v[ls_i]
                for k in range(1, tl_i - 1):
                    extra.append((v0, loop_v[ls_i + k], loop_v[ls_i + k + 1]))
            if extra:
                parts.append(np.asarray(extra, dtype=np.int64))
        faces = np.vstack(parts) if parts else np.zeros((0, 3), dtype=np.int64)
        return verts, faces

    def object_world_matrix(self, obj_entry) -> np.ndarray:
        _, obj_blk = obj_entry
        return self.read_floats(obj_blk[5], 'Object', 'obmat').reshape(4, 4).T.astype(np.float64)

    def all_objects(self) -> dict:
        out = {}
        for oidx, blk in self.by_code.get(b'OB\x00\x00', []):
            otype = self.read_int(blk[5], 'Object', 'type')
            oname = self.read_id_name(blk[5], 'Object')
            if oname.startswith('OB'):
                oname = oname[2:]
            dptr = self.read_ptr(blk[5], 'Object', 'data')
            data_entry = self.id_by_old.get(dptr) if dptr else None
            out[oname] = (otype, (oidx, blk), data_entry)
        return out

    def collection_objects(self, cname: str) -> list[str]:
        for cidx, blk in self.by_code.get(b'GR\x00\x00', []):
            name = self.read_id_name(blk[5], 'Collection')
            if name.startswith('GR'):
                name = name[2:]
            if name == cname:
                owned = self._owned_data_map(cidx)
                objs = []
                for cobj in self.iter_listbase(blk[5], 'Collection', 'gobject', lookup=owned):
                    optr = self.read_ptr(cobj[5], 'CollectionObject', 'ob')
                    if optr and optr in self.id_by_old:
                        oname = self.read_id_name(self.id_by_old[optr][1][5], 'Object')
                        if oname.startswith('OB'):
                            oname = oname[2:]
                        objs.append(oname)
                return objs
        raise ValueError(f'Collection {cname!r} not found')


def _clean_mesh(verts: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Remove repeated faces, degenerate zero-area triangles, and unreferenced vertices; orient closed shells."""
    f = import_hra._dedupe_repeated_faces(verts, np.asarray(faces, dtype=np.int64))
    zmask = import_hra._zero_area_mask(verts, f)
    if np.any(zmask):
        f = f[~zmask]
    # Compact unused vertices
    used, inv = np.unique(f, return_inverse=True)
    v = verts[used].copy()
    f = inv.reshape(-1, 3)
    f = import_hra._orient_closed_shell_outward(v, f)
    return v, f


def _target_face_count(nf: int) -> int:
    """Conservative triangle budget keeping small/medium muscles untouched and large multi-slip sheets smooth."""
    if nf <= 2200:
        return nf
    if nf <= 10000:
        return max(2200, int(round(nf * 0.45)))
    return min(5500, max(3200, int(round(nf * 0.22))))


def _maybe_simplify(verts: np.ndarray, faces: np.ndarray, use_qem: bool) -> tuple[np.ndarray, np.ndarray]:
    v, f = _clean_mesh(verts, faces)
    if not use_qem:
        return v, f
    target = _target_face_count(len(f))
    if target >= len(f):
        return v, f
    import fast_simplification
    sv, sf = fast_simplification.simplify(v.astype(np.float32), f.astype(np.int32), target_count=target, agg=7)
    sv64 = np.asarray(sv, dtype=np.float64)
    sf64 = np.asarray(sf, dtype=np.int64)
    return _clean_mesh(sv64, sf64)


def _apply_world_to_yup(verts_local: np.ndarray, faces_local: np.ndarray, M: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    vw = verts_local @ M[:3, :3].T + M[:3, 3]
    vt = np.empty_like(vw)
    vt[:, 0] = vw[:, 0]
    vt[:, 1] = vw[:, 2]
    vt[:, 2] = -vw[:, 1]
    f = faces_local[:, [0, 2, 1]].copy() if np.linalg.det(M[:3, :3]) < 0.0 else faces_local.copy()
    return vt, f


def rebuild_otot(bf: BlendFile, use_qem: bool = True):
    all_objs = bf.all_objects()
    mus_names = sorted(set(bf.collection_objects('4: Muscular system')))

    # Cache canonical local mesh simplification by Blender Mesh `old` pointer so .l/.r twins stay 100% symmetric!
    local_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    packed_meshes = []
    named_centroids = {}
    items_map = collections.OrderedDict()

    stats = {'raw_faces': 0, 'final_faces': 0, 'qem_simplified': 0}

    for raw_name in mus_names:
        if raw_name not in all_objs:
            continue
        otype, obj_entry, mesh_entry = all_objs[raw_name]
        if otype != 1 or mesh_entry is None:
            continue
        if raw_name.endswith(('.j', '.g')):
            continue
        raw_base = re.sub(r'\.[a-z0-9]+$', '', raw_name)
        if NON_MUSCLE_RE.search(raw_base) and 'tensor fasciae latae' not in raw_base.lower():
            continue

        # Fix upstream Z-Anatomy defects cleanly:
        # 1. Ascending/Descending Trapezius parts are swapped in upstream Startup.blend (verified via Y centroids).
        fixed_name = raw_name
        if raw_name.startswith('Ascending part of trapezius muscle'):
            fixed_name = raw_name.replace('Ascending part of trapezius muscle', 'Descending part of trapezius muscle', 1)
        elif raw_name.startswith('Descending part of trapezius muscle'):
            fixed_name = raw_name.replace('Descending part of trapezius muscle', 'Ascending part of trapezius muscle', 1)

        norm_name = fixed_name.replace(' ', '_')
        mesh_old = mesh_entry[1][2]
        if mesh_old not in local_cache:
            lv, lf = bf.extract_mesh_local(mesh_entry)
            stats['raw_faces'] += len(lf)
            sv, sf = _maybe_simplify(lv, lf, use_qem=use_qem)
            if len(sf) < len(lf):
                stats['qem_simplified'] += 1
            local_cache[mesh_old] = (sv, sf)
        else:
            sv, sf = local_cache[mesh_old]
            stats['raw_faces'] += len(sf)

        M = bf.object_world_matrix(obj_entry)
        vt, fa = _apply_world_to_yup(sv, sf, M)
        vt, fa = _clean_mesh(vt, fa)
        if len(vt) == 0 or len(fa) == 0:
            raise ValueError(f'Empty geometry after cleaning for {raw_name}')

        # 2. Upstream Z-Anatomy left Iliocostalis colli lacks .l suffix despite sitting at X = +53.6 mm.
        b, s, side, t = cls.split(norm_name)
        if norm_name == 'Iliocostalis_colli_muscle' and float(vt[:, 0].mean()) > 0.02:
            norm_name = 'Iliocostalis_colli_muscle.l'
            b, s, side, t = cls.split(norm_name)

        # Strip outer parens cleanly on standalone parenthesized muscles like (Adductor_minimus)
        if b.startswith('(') and b.endswith(')') and b not in MULTI_HEAD_PARENT:
            clean_b = b[1:-1]
            norm_name = f'{clean_b}.{side}' if side else clean_b
            b = clean_b

        if t != 'p':
            raise ValueError(f'Unexpected enthesis/origin suffix in muscular system: {norm_name}')

        mesh_idx = len(packed_meshes)
        packed_meshes.append((norm_name, vt, fa))
        named_centroids[norm_name] = tuple(vt.mean(axis=0).tolist())
        stats['final_faces'] += len(fa)

        # Group multi-head bellies under their canonical anatomical muscle entry
        parent_id = MULTI_HEAD_PARENT.get(b, b)
        entry = items_map.setdefault(parent_id, {'p': [], 's': set()})
        entry['p'].append(mesh_idx)
        if side:
            entry['s'].add(side)

    # Hard anatomical polarity & Trapezius vertical-order gate
    cls.validate_bilateral_polarity(named_centroids)

    # Build sidebar groups using gen2 conventions (zero Lainnya items!)
    groups_by_reg = [[] for _ in gen2.MR]
    for bid, it in items_map.items():
        k = gen2.norm(bid)
        label, latin = gen2.MUS.get(k, (gen2.cleaned(bid), ''))
        rg = gen2.mreg(k)
        if rg == 5:
            raise ValueError(f'Muscle {bid!r} (key={k!r}) fell into Lainnya — add region mapping in gen2.MRX')
        d = None
        gen_flag = 0
        if k == 'biceps_brachii':
            d = 'biceps'
        elif k == 'deltoid':
            d = 'deltoid'
        elif re.search(r'rectus_femoris|vastus', k):
            d = 'quadriceps'
            gen_flag = 1
        eng = 'Buccinator muscle' if k == 'bucinator' else gen2.cleaned(bid)
        item = {
            'id': bid,
            'n': label,
            'l': latin,
            'e': eng,
            'r': gen2.MR[rg],
            's': gen2.sidestr(it['s']),
            'p': it['p'],
        }
        if d:
            item['d'] = d
        if gen_flag:
            item['g'] = 1
        groups_by_reg[rg].append(item)

    sidebar = [
        {'g': gen2.MR[i], 'items': sorted(groups_by_reg[i], key=lambda o: o['n'].lower())}
        for i in range(len(gen2.MR))
        if groups_by_reg[i]
    ]
    bundle = import_hra.pack(packed_meshes, layer='otot', sidebar_groups=sidebar)
    return bundle, {'g': sidebar, 'gen': bundle['gen']}, stats


def _rechunk_vessel_sidebar(layer_cfg: dict, chunk_size: int = 22) -> list[dict]:
    """Keep Pembuluh Utama first and re-bucket remaining items alphabetically with clean labels."""
    main_items = []
    other_items = []
    for grp in layer_cfg['g']:
        if grp['g'] == 'Pembuluh Utama':
            main_items.extend(grp['items'])
        else:
            other_items.extend(grp['items'])
    main_items.sort(key=lambda o: o['n'].lower())
    other_items.sort(key=lambda o: o['n'].lower())

    out = []
    if main_items:
        out.append({'g': 'Pembuluh Utama', 'items': main_items})
    for start in range(0, len(other_items), chunk_size):
        chunk = other_items[start:start + chunk_size]
        a = re.sub(r'^[^A-Za-z]+', '', chunk[0]['n'])[:1].upper() or '?'
        b = re.sub(r'^[^A-Za-z]+', '', chunk[-1]['n'])[:1].upper() or '?'
        label = a if a == b else f'{a}–{b}'
        out.append({'g': label, 'items': chunk})
    return out


def _remap_and_pack_vessel(layer: str, meshes: list[tuple[str, np.ndarray, np.ndarray]], items: list[dict], main_ids: set[str]):
    """Pack vessel layer meshes and rebuild sidebar groups cleanly."""
    main_grp = {'g': 'Pembuluh Utama', 'items': [it for it in items if it['id'] in main_ids]}
    other_grp = {'g': 'Other', 'items': [it for it in items if it['id'] not in main_ids]}
    sidebar = _rechunk_vessel_sidebar({'g': [main_grp, other_grp]})
    bundle = import_hra.pack(meshes, layer=layer, sidebar_groups=sidebar)
    return bundle, {'g': sidebar, 'gen': bundle['gen']}


def repair_vessels(bf: BlendFile, layers: dict):
    """Apply source-verified Z-Anatomy fixes to vsTo, vsAb, vsKv, and vsLe."""
    all_objs = bf.all_objects()

    # Verify in Startup.blend that Transverse sinus.r and Axillary vein.l are exact X-mirrors across X=0
    for base in ('Transverse sinus', 'Axillary vein'):
        ml = bf.object_world_matrix(all_objs[f'{base}.l'][1])
        mr = bf.object_world_matrix(all_objs[f'{base}.r'][1])
        expected_mr = ml.copy()
        expected_mr[0, :] *= -1.0
        if not np.allclose(mr, expected_mr, atol=1e-4):
            raise ValueError(f'{base}.l/.r in Startup.blend are not exact X-mirrors:\n{ml}\nvs\n{mr}')

    updated_bundles = {}
    updated_cfgs = {}

    # 1. vsKv: recover Transverse_sinus.r by exact X-mirror of Transverse_sinus.l
    vskv_meshes = [(m[0], m[1], m[2]) for m in vg.decode_v2_bundle(json.loads((ROOT / 'data/atlas_vsKv.json').read_bytes()))]
    ts_l_idx = next(i for i, m in enumerate(vskv_meshes) if m[0] == 'Transverse_sinus.l')
    _, ts_v, ts_f = vskv_meshes[ts_l_idx]
    ts_r_v = ts_v.copy()
    ts_r_v[:, 0] = -ts_r_v[:, 0]
    ts_r_f = ts_f[:, [0, 2, 1]].copy()
    ts_r_idx = len(vskv_meshes)
    vskv_meshes.append(('Transverse_sinus.r', ts_r_v, ts_r_f))

    vskv_cfg = json.loads(json.dumps(layers['vsKv']))
    for grp in vskv_cfg['g']:
        for it in grp['items']:
            if it['id'] == 'Transverse_sinus':
                it['p'] = [ts_l_idx, ts_r_idx]
                it['s'] = 'kanan & kiri'
    b_kv = import_hra.pack(vskv_meshes, layer='vsKv', sidebar_groups=vskv_cfg['g'])
    vskv_cfg['gen'] = b_kv['gen']
    updated_bundles['vsKv'] = b_kv
    updated_cfgs['vsKv'] = vskv_cfg

    # 2. vsLe: recover Axillary_vein.l by exact X-mirror of Axillary_vein.r
    vsle_meshes = [(m[0], m[1], m[2]) for m in vg.decode_v2_bundle(json.loads((ROOT / 'data/atlas_vsLe.json').read_bytes()))]
    ax_r_idx = next(i for i, m in enumerate(vsle_meshes) if m[0] == 'Axillary_vein.r')
    _, ax_v, ax_f = vsle_meshes[ax_r_idx]
    ax_l_v = ax_v.copy()
    ax_l_v[:, 0] = -ax_l_v[:, 0]
    ax_l_f = ax_f[:, [0, 2, 1]].copy()
    ax_l_idx = len(vsle_meshes)
    vsle_meshes.append(('Axillary_vein.l', ax_l_v, ax_l_f))

    vsle_cfg = json.loads(json.dumps(layers['vsLe']))
    for grp in vsle_cfg['g']:
        for it in grp['items']:
            if it['id'] == 'Axillary_vein':
                it['p'] = [ax_r_idx, ax_l_idx]
                it['s'] = 'kanan & kiri'
    b_le = import_hra.pack(vsle_meshes, layer='vsLe', sidebar_groups=vsle_cfg['g'])
    vsle_cfg['gen'] = b_le['gen']
    updated_bundles['vsLe'] = b_le
    updated_cfgs['vsLe'] = vsle_cfg

    # 3. vsTo -> remove 3 orphaned coronary fragments; relocate Subcostal_artery & Inferior_phrenic_artery -> vsAb
    drop_ids = {
        'Circumflex_artery_of_heart',
        'Right_inferolateral_branch_of_right_coronary_artery',
        'Septal_branches_of_anterior_interventricular_artery',
    }
    move_ids = {'Subcostal_artery', 'Inferior_phrenic_artery'}

    vsto_orig = [(m[0], m[1], m[2]) for m in vg.decode_v2_bundle(json.loads((ROOT / 'data/atlas_vsTo.json').read_bytes()))]
    vsto_main_ids = {it['id'] for grp in layers['vsTo']['g'] if grp['g'] == 'Pembuluh Utama' for it in grp['items']}
    vsto_items_all = [json.loads(json.dumps(it)) for grp in layers['vsTo']['g'] for it in grp['items']]

    # Extract moved meshes + items before rebuilding vsTo
    moved_items = []
    moved_meshes = []
    vsto_kept_items = []
    vsto_new_meshes = []

    for it in vsto_items_all:
        if it['id'] in drop_ids:
            continue
        if it['id'] in move_ids:
            new_p = []
            for old_idx in it['p']:
                mname, mv, mf = vsto_orig[old_idx]
                if mname == 'Inferior_phrenic_artery':
                    mname = 'Inferior_phrenic_artery.r'
                new_p.append(len(moved_meshes))
                moved_meshes.append((mname, mv, mf))
            it['r'] = 'Abdomen & Pelvis'
            it['_rel_p'] = new_p
            moved_items.append(it)
            continue
        new_p = []
        for old_idx in it['p']:
            mname, mv, mf = vsto_orig[old_idx]
            if mname == 'Superior_phrenic_arteries':
                mname = 'Superior_phrenic_arteries.r'
            new_p.append(len(vsto_new_meshes))
            vsto_new_meshes.append((mname, mv, mf))
        it['p'] = new_p
        vsto_kept_items.append(it)

    b_to, cfg_to = _remap_and_pack_vessel('vsTo', vsto_new_meshes, vsto_kept_items, vsto_main_ids - drop_ids)
    updated_bundles['vsTo'] = b_to
    updated_cfgs['vsTo'] = cfg_to

    # 4. vsAb -> append Subcostal_artery & Inferior_phrenic_artery
    vsab_meshes = [(m[0], m[1], m[2]) for m in vg.decode_v2_bundle(json.loads((ROOT / 'data/atlas_vsAb.json').read_bytes()))]
    vsab_main_ids = {it['id'] for grp in layers['vsAb']['g'] if grp['g'] == 'Pembuluh Utama' for it in grp['items']}
    vsab_items = [json.loads(json.dumps(it)) for grp in layers['vsAb']['g'] for it in grp['items']]
    base_off = len(vsab_meshes)
    vsab_meshes.extend(moved_meshes)
    for it in moved_items:
        it['p'] = [base_off + k for k in it.pop('_rel_p')]
        vsab_items.append(it)

    b_ab, cfg_ab = _remap_and_pack_vessel('vsAb', vsab_meshes, vsab_items, vsab_main_ids)
    updated_bundles['vsAb'] = b_ab
    updated_cfgs['vsAb'] = cfg_ab

    return updated_bundles, updated_cfgs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('blend_path', type=Path, help='Path to Z-Anatomy Startup.blend')
    parser.add_argument('--no-qem', action='store_true', help='Skip QEM simplification on dense muscle meshes')
    args = parser.parse_args()

    page_path = ROOT / 'index.html'
    page = page_path.read_text(encoding='utf-8')
    layers, _ = json.JSONDecoder().raw_decode(page.split('const BL = ', 1)[1])

    with BlendFile(args.blend_path) as bf:
        otot_bundle, otot_cfg, otot_stats = rebuild_otot(bf, use_qem=not args.no_qem)
        vessel_bundles, vessel_cfgs = repair_vessels(bf, layers)

    layers['otot'] = otot_cfg
    for lk, cfg in vessel_cfgs.items():
        layers[lk] = cfg

    updated_page = import_hra.replace_page_data(page, 'BL', layers)

    # Atomic writes for all modified bundles + index.html
    import_hra.write_data(ROOT / 'data/atlas_otot.json', otot_bundle)
    for lk, bundle in vessel_bundles.items():
        import_hra.write_data(ROOT / f'data/atlas_{lk}.json', bundle)
    import_hra.write_data_atomic(page_path, updated_page)

    otot_sz = (ROOT / 'data/atlas_otot.json').stat().st_size / (1024 * 1024)
    otot_items = sum(len(g['items']) for g in otot_cfg['g'])
    print(f'otot: gen={otot_bundle["gen"]} items={otot_items} meshes={len(otot_bundle["m"]["meta"])} '
          f'faces={otot_stats["final_faces"]:,} (raw {otot_stats["raw_faces"]:,}, qem={otot_stats["qem_simplified"]}) '
          f'size={otot_sz:.2f} MiB')
    print('  otot groups:', [(g['g'], len(g['items'])) for g in otot_cfg['g']])
    for lk in ('vsKv', 'vsLe', 'vsTo', 'vsAb'):
        b = vessel_bundles[lk]
        sz = (ROOT / f'data/atlas_{lk}.json').stat().st_size / (1024 * 1024)
        n_items = sum(len(g['items']) for g in vessel_cfgs[lk]['g'])
        print(f'{lk:4s}: gen={b["gen"]} items={n_items:2d} meshes={len(b["m"]["meta"]):3d} size={sz:.2f} MiB')


if __name__ == '__main__':
    main()
