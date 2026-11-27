# Human Anatomy 3D Atlas

[Bahasa Indonesia](README.md) | **English**

A learning website for human anatomy with interactive 3D models. Users can rotate, zoom, and click structures directly (bones, muscles, nerves, organs, blood vessels, and the lymphatic system), then read the name (Indonesian, Latin, English), description, function, relations (innervation, blood supply, related structures), and clinical correlations.

> **Language note:** the application interface and the anatomical text are currently written in **Indonesian**. Latin and English names are shown alongside where available. This README is a translation of the Indonesian one.
>
> **Important:** the content is written for study purposes and is **not a substitute for medical references**. Please verify it against an anatomy textbook before using it as formal teaching material.

---

## Table of contents

1. [Features](#features)
2. [Data coverage](#data-coverage)
3. [Running and deploying](#running-and-deploying)
4. [Repository structure](#repository-structure)
5. [Technology used](#technology-used)
6. [How the project was developed](#how-the-project-was-developed)
7. [Data format](#data-format)
8. [Adding a new system or structure](#adding-a-new-system-or-structure)
9. [Known limitations](#known-limitations)
10. [Credits](#credits)
11. [License](#license)

---

## Features

- **Interactive 3D space**: rotate (drag), zoom (scroll or pinch), pan (right click), reset, and auto-rotate.
- **Hierarchical sidebar** with Skeleton, Muscles, Nerves, and Organs tabs, grouped by region or system, with search.
- **Click directly on the model** to select a structure, with a name label on hover (desktop).
- **Highlight or Isolate**: other structures are faded or hidden.
- **Side filter** for the right or left side of the body.
- **Skeleton context**: bones appear faintly behind muscles, nerves, and organs so their position is easy to understand.
- **Description panel** as a card that can be opened, closed, and resized; the sidebar can be opened, closed, and resized.
- **Light and dark themes** with a dotted background like a diagram canvas.
- **Per-system loading** downloads models as needed. The viewer keeps the skeleton and up to two other layers, and renders on demand when idle.
- Works on mobile (responsive layout).

## Data coverage

The main body views use Z-Anatomy models. HuBMAP references retain their source coordinates. The VOXEL-MAN testis is centred in its own view. The main skeleton overlay is disabled for both reference sources. [Model sources](data/NOTICE.md)

| System | Items | Meshes | Triangles | Notes |
|---|---:|---:|---:|---|
| Skeleton | 159 | 277 | 329 k | Bones and cartilage; ID/Latin/English names; full descriptions |
| Muscles | 212 | 462 | 845 k | Full 3D muscle bellies from Z-Anatomy (no enthesis stickers); Indonesian/Latin names for main muscles |
| Nerves | 120 | 237 | 78 k | Major nerves and portions of the spinal cord |
| Respiratory | 48 | 52 | 127 k | Lungs, airways, bilateral nasal and laryngeal cartilage, pleura and diaphragm |
| Larynx and trachea (HRA) | 11 | 15 | 64 k | Laryngeal cartilage, vocalis, tracheal rings, carina, and main bronchi |
| Digestive | 40 | 46 | 154 k | Mouth, salivary glands, GI tract, liver, biliary system, pancreas and omenta |
| Male reproductive | 10 | 15 | 22 k | Simplified testes and ducts |
| Testis (Visible Human) | 1 | 1 | 11 k | One adult testis from a 1 mm segmentation |
| Female reproductive (HRA) | 11 | 19 | 74 k | Uterus, cervix, ovaries, and uterine tube segments |
| Urinary (HRA) | 15 | 81 | 242 k | Kidneys (incl. renal hila), collecting system, ureters, bladder and male urethra |
| Endocrine | 10 | 13 | 31 k | Hypothalamus, pituitary, pineal, thyroid, parathyroids, adrenals, thymus |
| Heart and great vessels (HRA) | 46 | 51 | 317 k | Four chambers, four valves, septum, coronary vessels (incl. LCx) and great vessels |
| Blood vessels (6 regions) | 369 | 629 | 3.5 M | Regional arteries and veins |
| Lymphatic organs (HRA) | 2 | 7 | 20 k | Spleen and thymus |
| Lymph node (HRA) | 7 | 13 | 254 k | Parts of one lymph node |
| Small intestine (HRA) | 7 | 10 | 34 k | Duodenal ampulla, duodenum, sphincter of Oddi, minor papilla, jejunum, ileum and terminal ileum |
| Large intestine (HRA) | 10 | 10 | 34 k | Cecum, ileocecal valve, appendix, colon, colic flexures and rectum |

Level of explanation:

- **Detailed** (description, function, innervation, blood supply, related structures, clinical correlations): many bones, organs, and major vessels.
- The sidebar marks general descriptions. Entries with limited content show a location or group.

## Running and deploying

The page loads `data/*.json` with `fetch`, so it **cannot be opened through `file://`**. Use any static server.

### Locally

```bash
git clone <your-repo-url>
cd <repo-name>
python3 -m http.server 8000
# open http://localhost:8000
```

### GitHub Pages

1. Push the entire repository contents.
2. Settings, then Pages.
3. Source: *Deploy from a branch*, branch `main`, folder `/ (root)`.
4. The site is available at `https://<username>.github.io/<repo>/`.

The model bundles total about 72.3 MiB. The largest file is `atlas_vsKa.json` at about 15.5 MiB.

## Repository structure

```
.
├── index.html          # The app (HTML, CSS, JS in a single file)
├── LICENSE             # Code license (MIT)
├── README.md           # Indonesian README
├── README.en.md        # English README
├── ANATOMY-REVIEW.md   # Initial anatomy audit & follow-up notes
├── data/
│   ├── LICENSE             # Full CC BY-SA 4.0 text (data and text)
│   ├── NOTICE.md           # Data origin, changes, and attribution
│   ├── atlas_rangka.json   # skeleton
│   ├── atlas_otot.json     # muscles
│   ├── atlas_saraf.json    # nerves
│   ├── atlas_organ.json    # respiratory
│   ├── atlas_cerna.json    # digestive
│   ├── atlas_repro.json    # male reproductive
│   ├── atlas_reproF.json   # female reproductive reference
│   ├── atlas_testisRef.json # Visible Human testis reference
│   ├── atlas_airway.json   # larynx and trachea reference
│   ├── atlas_urin.json     # urinary (HRA)
│   ├── atlas_endo.json     # endocrine
│   ├── atlas_jantung.json  # heart and great vessels (HRA)
│   ├── atlas_vsKa.json     # vessels: head-neck (arteries)
│   ├── atlas_vsKv.json     # vessels: head-neck (veins)
│   ├── atlas_vsTo.json     # vessels: thorax
│   ├── atlas_vsAb.json     # vessels: abdomen and pelvis
│   ├── atlas_vsLe.json     # vessels: arm and hand
│   ├── atlas_vsTu.json     # vessels: leg and foot
│   ├── atlas_limfa.json    # HRA spleen and thymus
│   ├── atlas_limfonodus.json # HRA lymph node
│   ├── atlas_ususHalus.json  # HRA small intestine
│   └── atlas_ususBesar.json  # HRA large intestine
├── docs/
│   ├── GEOMETRY-VALIDATION.md  # Three-tier geometry validation report
│   └── research/               # Primary-source specs (glTF/WebGL, WCAG, TA2/EYD V)
└── tools/              # Offline Python model-processing and validation scripts
```

Data file names follow the layer keys in `index.html` (`atlas_<key>.json`).

## Technology used

**Application (front-end)**

- Plain HTML, CSS, and JavaScript (no framework and no build step), all in a single `index.html`.
- [three.js](https://threejs.org/) r128 for 3D rendering (`MeshStandardMaterial`, `Raycaster`), loaded from the cdnjs CDN.
- `OrbitControls` from the `three@0.128.0` package (jsDelivr CDN) for rotate, zoom, and pan.
- CSS variables for the light and dark themes, `ResizeObserver` to fit the canvas, Pointer Events for panel dragging and model clicking.

**Data processing (tools, offline)**

- Python 3 with `numpy` (and `scipy` available) to read OBJ files, remove duplicates, simplify meshes, and pack binary data.
- Node.js to check script syntax and rebuild the data block of the page.

**Hosting**

- The development version was published as a web page with separate data files.
- The version in this repository uses relative `data/…` paths, so it suits GitHub Pages or any other static server.

**Development**

- The project was developed iteratively together with an AI assistant (Claude, Anthropic): architecture design, code, model-processing scripts, and the anatomy text. See [Credits](#credits) and [Known limitations](#known-limitations) regarding content verification.

## How the project was developed

The order of work, from the beginning to now:

1. **Content design.** Define the outline: cells and tissues, eleven organ systems, regional anatomy, and a uniform data structure for every structure (ID/Latin/English names, category and location, description and function, relations, clinical correlations).
2. **Interface prototype.** A two-part layout: sidebar on the left, 3D space and description panel on the right. The first version used simple procedural 3D shapes (cylinders and spheres) as a placeholder.
3. **Real models.** The Z-Anatomy OBJ file (the whole atlas, about 1.3 GB, 4,878 objects) was processed into data light enough for the web.
4. **Layers added step by step**: skeleton, then muscles and nerves, then organs by system, then blood vessels and the lymphatic system.
5. **Interface improvements**: light and dark theme, dotted background, direct clicking on the model, highlight and isolate, side filter, resizable panels, mobile layout fixes.
6. **Per-system data separation (lazy loading)** to keep the page small and let new systems be added without a single-file size limit.

### Model processing pipeline (`tools/`)

1. **Extraction**: read the OBJ line by line (streaming) and keep the chosen objects, selected by order index and name pattern.
2. **Selection**: choose object ranges for each system. For example, bones from the start indices, organs from the viscera range, vessels from the artery and vein range.
3. **Duplicate removal**: many tubular structures (ureters, urethra, some bronchi and ducts, almost all vessels) are stored as two identical objects in the source. Objects with identical geometry are dropped.
4. **Simplification**: for the skeleton, muscles, nerves, respiratory, and digestive systems, meshes are simplified with *vertex clustering* (merging vertices on a grid) with a per-object triangle target. The other packed meshes preserve source triangles. Meshes that exceed the 16-bit index limit are split at triangle boundaries.
5. **Quantization and packing (`ha-mesh-v2`)**: each structure is packed with per-mesh anisotropic `uint16` quantization (with automatic promotion to IEEE-754 `float32` on thin/sliver meshes whenever quantization would introduce any new zero-area triangle, >1.0° p99 normal tilt, or >5.0 µm vertex drift), 16-bit triangle indices (`<= 65,535` vertices per chunk to avoid WebGL 2.0 primitive-restart index `65535`), bound via a `gen` digest, then base64-encoded into JSON.
6. **Grouping and naming**: structures are grouped by side, type, or region; Indonesian (EYD V / KBBI VI) and Latin (*Terminologia Anatomica*, 2nd ed. / TA2) names are written for main structures.
7. **Writing content**: description, function, innervation, blood supply, related structures, and clinical correlations are written per structure or per group.

### Design decisions

- **A single HTML file with no build step** so it is easy to host and understand.
- **Separate data per system** so the initial page stays compact (about 400 KB) and a model is downloaded only when needed.
- **Structures lying on the surface of other structures** (liver segments, taeniae coli) are hidden until selected, to avoid flickering from coincident surfaces.
- **Thin membranes** (pleura, mucosa, omenta, mesocolon) are drawn transparent and excluded from clicking on the model so they do not block structures behind them.
- **Vessel regions** use anatomical assignments for named structures and position-based grouping for the remaining meshes.

## Data format

Each `data/atlas_<key>.json` uses the versioned little-endian `ha-mesh-v2` format (the viewer also retains validated backward compatibility with legacy v1 bundles):

```json
{
  "v": 2,
  "fmt": "ha-mesh-v2",
  "endian": "le",
  "gen": "<16-hex SHA-256 ordinal digest matching BL[key].gen>",
  "b": "<base64 little-endian binary>",
  "m": {
    "mn": [x, y, z],
    "sc": 1.7,
    "meta": [["Object_name.r", vertexCount, triangleCount, vertexByteOffset, indexByteOffset, "u16|f32", [ox, oy, oz], [sx, sy, sz]], "..."]
  }
}
```

- Binary blocks are laid out contiguously in little-endian byte order: all 4-byte-aligned `float32` vertex blocks first (`12 B/vertex`), then 2-byte-aligned per-mesh quantized `uint16` vertex blocks (`6 B/vertex`), then 2-byte-aligned `uint16` triangle index blocks (`6 B/triangle`, with `vertexCount <= 65535` so indices never emit `65535`, reserved in WebGL 2.0 for primitive restart).
- For `u16` meshes, world position is computed per axis as `ox + value / 65535 × sx` (decoded explicitly via `DataView.getUint16(..., true)`); `f32` meshes store exact IEEE-754 coordinates (`DataView.getFloat32(..., true)`).
- `gen` binds each JSON geometry bundle to its sidebar ordinal mapping (`BL[key].gen`) in `index.html`; the viewer validates format version, byte order, generation hash, finite bounds, buffer ranges, face indices, and sidebar references before attaching any mesh to the scene.
- The lists of names, groups, and description text are in `index.html`:
  - `BL[key].g`: sidebar groups and items (`id`, `n` main name, `l` Latin, `e` English, `r` region, `s` side, `p` mesh indices, `d` description key, `g` when the explanation is general).
  - `DET[key]`: text (`desc`, `fn`, `nerve`, `blood`, `rel`, `clin`).
  - Geometry file paths are derived directly from the layer key (`data/atlas_<key>.json`).

## Adding a new system or structure

1. **Extract and pack** objects from the OBJ with the scripts in `tools/` to produce `data/atlas_<key>.json` and the mesh list.
2. **Create item groups** with `id` (base object name), `n`, `l`, `e`, `r`, `s`, `p` (mesh indices), and `d` (text key).
3. **Add text** to `DET` (six fields), or use a general key with `g: 1`.
4. **Register the layer** in `index.html`:
   - add `BL[key]`,
   - add the key to `NAMES`, `TITLE`, `LATIN`, `HELP`, and `EM`,
   - add an option in the organ-system dropdown.
5. **Color**: adjust the `ocol` function if you need specific per-structure colors.

> The scripts in `tools/` are for reference: they use local paths and need the source OBJ file (not included because of its size). Adjust the paths before running them.

Use [the HuBMAP import instructions](data/NOTICE.md#hubmap-reference-models) to regenerate the reference views, and validate source-vs-packed geometry gates with `python3 tools/validate_geometry.py <source-dir>` (recorded in [docs/GEOMETRY-VALIDATION.md](docs/GEOMETRY-VALIDATION.md)).

## Known limitations

- The main atlas uses a male body model. The female reproductive reference uses the Visible Human Female coordinate frame.
- Coverage gaps include the anal canal, chordae tendineae, SA and AV nodes, pericardium, alveoli, complete vocal folds, and whole-body lymphatic vessels and nodes. The simplified male reference has small testis meshes and a gap at the junction of the reproductive ducts. [Source and measurement notes](data/NOTICE.md)
- **Upstream Z-Anatomy source asymmetries**: direct inspection of `Z-Anatomy/Startup.blend` confirms that `Vagus_nerve_(X).l` terminates at T4/aortic arch level upstream (whereas `Vagus_nerve_(X).r` continues into the abdomen), phrenic vessels (`Superior_phrenic_arteries.r`, `Right_superior_phrenic_vein`, `Inferior_phrenic_artery.r`) are modeled on the right side only, and `Articularis_genus` exists only as origin patches without a muscle-belly mesh.
- **General explanations** for most minor blood vessels, muscles, and nerves outside the main structures. Some names come from English source labels.
- **Model quality**: the skeleton, muscles (gentle QEM only on dense sheets >2,200 triangles via [`tools/rebuild_z_anatomy.py`](tools/rebuild_z_anatomy.py)), nerves, respiratory, and digestive systems were simplified; microscopic detail is reduced compared with the raw source.
- **Content verification**: anatomy explanations have been verified against primary references (StatPearls/NCBI Bookshelf, FIPAT *Terminologia Anatomica* TA2, EYD V / KBBI VI), but have not yet undergone formal peer review by an anatomist or clinician. Verify against textbooks before formal teaching.
- **Performance**: the head-neck arteries layer is about 15.5 MiB and 1.34 million triangles; it may feel heavy on older devices.

## Credits

- **[HuBMAP Human Reference Atlas (HRA)](https://humanatlas.io/3d-reference-library)** supplies eight reference layers under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credits include **Kristen Browne**, **Heidi Schlehlein**, and **Arie Kaufman (Stony Brook University)** for the large intestine. [Source DOIs and release files](data/NOTICE.md)
- **[Z-Anatomy](https://github.com/Z-Anatomy/Models-of-human-anatomy)**: source of the main body 3D models (Blender/OBJ), licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **BodyParts3D**: © The Database Center for Life Science (DBCLS), Japan. The 3D model database on which Z-Anatomy is based (<https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html>).
- **[three.js](https://threejs.org/)**: 3D rendering library (MIT license), including `OrbitControls`.
- **[FIPAT *Terminologia Anatomica* (TA2)](https://fipat.library.dal.ca/ta2/)**: international anatomical terminology standard used for Latin and English names.
- **EYD V & KBBI VI (Badan Bahasa, Indonesia)**: orthographic and standard-term references for Indonesian medical copy.
- **AI assistants (Claude, Anthropic & Antigravity)**: assisted with architecture, coding, model validation/processing scripts, and anatomical text authoring/editing.

Suggested attribution text to show on the site or in slides:

> 3D models: BodyParts3D © The Database Center for Life Science, via Z-Anatomy (CC BY-SA 4.0), and HuBMAP Human Reference Atlas (CC BY 4.0 — Kristen Browne, Heidi Schlehlein, Arie Kaufman / Stony Brook University), packed for the web.

## License

**This section is not legal advice.** Please re-check the original license terms before publishing or using the project commercially.

**Summary:** the application code is licensed **MIT**; Z-Anatomy-derived models and anatomy text are licensed **CC BY-SA 4.0**. HuBMAP reference models are licensed **CC BY 4.0**. License files: [`LICENSE`](LICENSE) (MIT, repository root), [`data/LICENSE`](data/LICENSE) (full CC BY-SA 4.0 text), and [`data/NOTICE.md`](data/NOTICE.md) (data origin, changes, attribution).

| Component | License | Notes |
|---|---|---|
| Z-Anatomy-derived 3D models (`data/`) | **CC BY-SA 4.0** (derived from Z-Anatomy and BodyParts3D) | Attribution is required and derivative works must be shared under the same license (*share-alike*). The models here have been selected, deduplicated, quantized, and partly simplified, so they count as derivative works. |
| Application code (logic in `index.html`, `tools/`) | **MIT** | The `LICENSE` file at the repository root. Covers the code only, not the model data or the anatomy text. |
| Description and translation text (inside `index.html`) | **CC BY-SA 4.0** | Matches the model data license. The text is embedded in `index.html` together with the code, so that file carries two licenses: code logic MIT, anatomy text CC BY-SA 4.0. |
| HuBMAP reference models | **CC BY 4.0** | The credits and source versions are listed in [data/NOTICE.md](data/NOTICE.md). |
| three.js | MIT | Loaded from a CDN. |

### Source license terms (Z-Anatomy)

License: [Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).

Statement in the Z-Anatomy README (quoted as written):

> With regard to this content, you are licensed to:
> * freely access part or whole of this database, and acquire data;
> * freely redistribute part or whole of the data from this database;
> * and freely create and distribute database and other derivative works based on part or whole of the data from this database, under the license, as long as you comply with the following conditions:
> * You must attribute this database in the manner specified by the author or licensor when distributing part or whole of this database or any derivative work.
> * You must distribute any derivative work based on part or whole of the data from this database under the same license.

What this means for this project:

- You **may** access, redistribute, and create derivative works from the model data.
- **Attribution is required**, in the manner specified by the licensor, whenever you distribute the data or a derivative work. The quote above does not detail the attribution format, so check the Z-Anatomy README or official page for the requested format. The attribution text in [Credits](#credits) is an initial suggestion.
- **Derivative works must use the same license** (CC BY-SA 4.0). The `data/` folder in this repository is a derivative work, so it must be licensed CC BY-SA 4.0.

Things to keep in mind:

1. **Per-part upstream licenses (verified from `Z-Anatomy/License.txt`).** BodyParts3D v4.0 uses CC BY 4.0 (earlier releases cited by Z-Anatomy used CC BY-SA 2.1 Japan). Z-Anatomy overall uses CC BY-SA 4.0, with specific upstream component licenses noted in its `License.txt`:
   - *Kidney* (Lissie Cowley, CC-BY-NC 4.0): **no longer shipped** in this project; the urinary layer now uses **HuBMAP (CC BY 4.0)** models.
   - *Anatomy of the Inner Ear* (University of Dundee School of Medicine, **CC-BY-NC-SA 4.0**): non-commercial license. Audit auditory ossicles (`Malleus`, `Incus`, `Stapes`) and `Cochlear`/`Vestibular` nerves before any commercial use.
   - *Cranial Nerves and Foramina* (University of Dundee, CAHID): CC-BY 4.0.
2. **Complete the license files.** Make sure `LICENSE` (MIT) has the correct year and copyright holder, and `data/LICENSE` contains the full CC BY-SA 4.0 text copied from the Creative Commons site.
3. **Keep the attribution** on the site (for example in the footer or an info panel) and in the README.

---

*Created for educational purposes. If you find an anatomical or naming error, please open an issue or send a correction.*
