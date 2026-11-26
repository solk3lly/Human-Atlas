import collections
import re

EXC = re.compile(
    r'(?:^|_)(?:ligament|ligaments|capsule|disc|nucleus|annulus|joint|bursa|bursae|fascia|fasciae|membrane|cartilage|'
    r'tendon|tendons|tendinous|aponeurosis|aponeuroses|retinaculum|sheath|sheaths|septum|septa|raphe|region|node|'
    r'artery|arteries|vein|veins|nerve|nerves|plexus|duct|ducts|gland|glands|ventricle|atrium|valve|papillary|heart|'
    r'vessel|vessels|trunk|space|canal|fossa|sinus|vertebra|bone|bones|meniscus|labrum|synovial|pulley|trochlea|'
    r'band|plate|fat|skin|cavity|foramen|hiatus|ring|arch|sulcus|lobe|cortex|tract|frenulum|linea|cord|symphysis|'
    r'tarsus|vena|insertion|insertions|zona)(?:$|_)',
    re.I,
)

# Lazily loaded when names.txt exists in cwd (keeps module importable for unit tests)
_NAMES_CACHE = None


def load_names(path='names.txt'):
    global _NAMES_CACHE
    if _NAMES_CACHE is None:
        with open(path, encoding='utf-8') as f:
            _NAMES_CACHE = [l.strip() for l in f]
    return _NAMES_CACHE


def __getattr__(attr):
    if attr == 'names':
        return load_names()
    if attr == 'mend':
        ns = load_names()
        return _muscle_range_end(ns)
    raise AttributeError(f'module {__name__!r} has no attribute {attr!r}')


def split(n):
    m = re.search(r'\.([a-z0-9]+)$', n)
    s = m[1] if m else ''
    b = n[:m.start()] if m else n
    side = s[-1] if s and s[-1] in 'rl' else ''
    t = 'e' if s.startswith('e') else 'o' if s.startswith('o') else 'p'
    return b, s, side, t


def _muscle_range_end(names_list):
    return next(i for i, n in enumerate(names_list) if i > 1400 and re.search(r'arter|vein|ventric|atrium|valve', n, re.I))


def select_from_names(names_list):
    """Select 3D muscle bellies (strictly excluding .e*/.o* enthesis bone stickers) and nerves."""
    mend = _muscle_range_end(names_list)
    mus, ner = [], []
    for i, n in enumerate(names_list):
        b, s, side, t = split(n)
        if 280 <= i < mend and (not EXC.search(b) or 'tensor_fasciae_latae' in b.lower()):
            mus.append((i, b, s, side, t))
        elif re.search(r'nerve|plexus|Spinal_cord|ganglion', b, re.I) and not re.search(
            r'venous|choroid|arter|vein|nucleus|vessel|root|node|lymph|tract|region|sulcus|canal|ridge|fossa|foramen|groove',
            b,
            re.I,
        ):
            ner.append((i, b, s, side, t))

    # Muscle deduplication: keep ONLY actual muscle bellies ('p'), NEVER .e* insertion or .o* origin bone patches.
    g = collections.defaultdict(list)
    for x in mus:
        g[(x[1], x[3])].append(x)
    keep = []
    for k, v in g.items():
        bellies = [x for x in v if x[4] == 'p']
        if bellies:
            keep.extend(bellies)

    bases = {x[1].lower().replace('_muscle', '') for x in keep}
    out = []
    for x in keep:
        par = re.sub(r'^.*?_(heads?|parts?|belly|bellies)_of_', '', x[1]).lower().replace('_muscle', '')
        if par != x[1].lower().replace('_muscle', '') and par in bases and not par.startswith('('):
            continue
        out.append(x)
    return out, ner


def select():
    return select_from_names(load_names())


def validate_bilateral_polarity(named_centroids, tol_m=0.01):
    """Verify anatomical X-polarity (+X left, -X right) and cranial-caudal Trapezius ordering.

    Catches Z-Anatomy upstream .el/.er left-right swaps (32 meshes in legacy builds) and the
    swapped Ascending/Descending Trapezius parts before packing.
    """
    errors = []
    for name, (cx, _cy, _cz) in named_centroids.items():
        _, _, side, _ = split(name)
        if side == 'l' and cx < -tol_m:
            errors.append(f'{name}: .l mesh sits on anatomical right (X={cx:+.4f}m)')
        elif side == 'r' and cx > tol_m:
            errors.append(f'{name}: .r mesh sits on anatomical left (X={cx:+.4f}m)')

    # Cranial-caudal order check for Trapezius (Descending/upper fibers must sit superior to Ascending/lower fibers)
    for side in ('r', 'l'):
        desc_k = f'Descending_part_of_trapezius_muscle.{side}'
        asc_k = f'Ascending_part_of_trapezius_muscle.{side}'
        if desc_k in named_centroids and asc_k in named_centroids:
            y_desc = named_centroids[desc_k][1]
            y_asc = named_centroids[asc_k][1]
            if y_desc <= y_asc:
                errors.append(
                    f'Trapezius.{side} vertical swap: Descending Y={y_desc:.3f}m <= Ascending Y={y_asc:.3f}m'
                )

    if errors:
        raise ValueError('Anatomical polarity validation failed:\n  - ' + '\n  - '.join(errors))


if __name__ == '__main__':
    m, n = select()
    print(_muscle_range_end(load_names()), len(m), len(n))
    import random
    random.seed(1)
    print([x[1] for x in random.sample(m, min(45, len(m))) if 'muscle' not in x[1].lower()])
    print(sorted({x[1] for x in m if 'uscle' not in x[1]})[:90])
