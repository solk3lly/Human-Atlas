# Data notice (folder `data/`)

The main body layers contain 3D model data derived from:

- **Z-Anatomy**, licensed under CC BY-SA 4.0 (https://github.com/Z-Anatomy)
- **BodyParts3D**, © The Database Center for Life Science (DBCLS), Japan

The data has been **modified**: objects were selected, exact duplicate meshes and within-mesh repeated faces removed, closed shells oriented outward, coplanar origin/enthesis bone stickers stripped (`Diaphragm.o*` in `organ`; `otot` rebuilt directly from Z-Anatomy `Startup.blend` collection `4: Muscular system` via `tools/rebuild_z_anatomy.py` with swapped Trapezius Ascending/Descending fixed and bilateral `Transverse_sinus.r` / `Axillary_vein.l` restored), dense meshes gently simplified, vertex positions quantized into `ha-mesh-v2`, and everything packed into a compact binary format encoded as base64 JSON.

## HuBMAP reference models

The six layers below use the [HuBMAP Human Reference Atlas 3D Reference Object Library](https://humanatlas.io/3d-reference-library), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit HuBMAP, Kristen Browne and Heidi Schlehlein, with the source records below. The reference views preserve the GLB transforms and metre units. The importer verifies pinned SHA-256 checksums, splits oversized meshes at triangle boundaries (`<= 65,535` vertices so `uint16` indices never emit the WebGL 2 primitive-restart value `65535`), and packs each structure into `ha-mesh-v2` using per-structure anisotropic `uint16` quantization with automatic promotion to IEEE-754 `float32` whenever quantization would introduce any new zero-area triangle, zero-normal vertex, >1.0° p99 normal error, or >5.0 µm vertex displacement.

| Atlas data | Source GLB files | Source record |
|---|---|---|
| `atlas_jantung.json` | `v1.1/VH_M_Heart.glb` | [Heart, male, Kristen Browne](https://doi.org/10.48539/HBM548.CTHS.699) |
| `atlas_urin.json` | `v1.2/VH_M_Kidney_L.glb`, `VH_M_Kidney_R.glb`, `VH_M_Ureter_L.glb`, `VH_M_Ureter_R.glb`, `VH_M_Urinary_Bladder.glb`, `VH_M_Urethra.glb` | [Urinary reference objects and credits](https://github.com/hubmapconsortium/ccf-releases/tree/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.2/markdown/ref-organs) · [Right ureter](https://doi.org/10.48539/HBM878.DBSR.759) |
| `atlas_limfa.json` | `v1.2/VH_M_Spleen.glb`, `VH_M_Thymus.glb` | [Spleen](https://doi.org/10.48539/HBM662.GMWC.569) · [Thymus](https://doi.org/10.48539/HBM823.SNLN.667) |
| `atlas_limfonodus.json` | `v1.2/NIH_M_Lymph_Node.glb` | [Lymph node, male](https://doi.org/10.48539/HBM299.VVXH.634) |
| `atlas_ususHalus.json` | `v1.2/VH_M_Small_Intestine.glb` | [Small intestine, male](https://github.com/hubmapconsortium/ccf-releases/blob/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.2/markdown/ref-organs/small-intestine-male.md) |
| `atlas_ususBesar.json` | `v1.2/SBU_M_Intestine_Large.glb` | [Large intestine, male, based on data from Arie Kaufman, Stony Brook University](https://doi.org/10.48539/HBM334.LVTH.937) |

To rebuild these layers, get the listed GLBs from the `models/` folder in the pinned [v1.1](https://github.com/hubmapconsortium/ccf-releases/tree/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.1/models) or [v1.2](https://github.com/hubmapconsortium/ccf-releases/tree/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.2/models) release. Place them in `v11/` and `v12/` subdirectories of a source directory and run `python3 tools/import_hra.py <source-directory>` from the repository (verify source-to-packed geometry with `python3 tools/validate_geometry.py <source-directory>`). The script uses NumPy and atomically updates the six packed data files and their sidebar mappings (`BL[layer].gen`). Normal website use requires only the shipped JSON files.

The original body geometry and the HuBMAP references use different coordinate frames and specimens. The viewer disables the original skeleton overlay for the reference layers. The heart shows complete valve objects, a septum, and the Left Circumflex Artery (LCx) split from upstream node `VH_M_diagonal_branch_of_left_anterior_descending_artery` (which HuBMAP's `v2.0/models/asct-b-3d-models-crosswalk.csv` maps to `FMA:3860`, but which geometrically courses posteriorly in the left AV sulcus `0.48 mm` from LMCA and `0.10 mm` from the Left Marginal Artery). The lymphatic views show the spleen, thymus, and parts of one lymph node. The bowel views show the ileum, cecum and rectum. The source collections do not provide separately selectable chordae tendineae, a whole-body lymphatic network, or the anal canal in these views. [Initial anatomy audit](../ANATOMY-REVIEW.md) · [Geometry validation report](../docs/GEOMETRY-VALIDATION.md) · [Terminology & remediation research](../docs/research/anatomy-terminology-and-remediation.md)

The HuBMAP ureter GLBs are double-walled hollow tubes (~0.5 mm wall thickness). Measured perpendicular to the local 3D centreline 20 mm distal to the ureteropelvic junction (UPJ), the left and right ureters measure **3.85 mm / 3.81 mm** outer equivalent diameter ($D_{\text{eq}}$) and **2.83 mm / 2.79 mm** inner lumen $D_{\text{eq}}$ (compared with horizontal axial spans of 4.49 mm / 4.46 mm, which inflate oblique tubes by ~17%). Clinical CT benchmarks depend on protocol: unenhanced CT averages 1.8 ± 0.9 mm with 96% ≤ 3 mm ([Zelenko et al., 2004](https://pubmed.ncbi.nlm.nih.gov/15039184/)), whereas delayed contrast-enhanced CT averages 4.3–4.4 mm with a 95th percentile of 6.9 mm ([Itanyi et al., 2020](https://link.springer.com/article/10.1186/s12301-020-00021-0)). Full station-by-station profiles and packing drift checks are recorded in [docs/GEOMETRY-VALIDATION.md](../docs/GEOMETRY-VALIDATION.md).

## License

The Z-Anatomy-derived data files are distributed under the
**Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)** license:
https://creativecommons.org/licenses/by-sa/4.0/

Under this license you may share and adapt the data, provided that:

1. you give appropriate **attribution** (see below), indicate if changes were made, and
2. you distribute any derivative work under the **same license** (CC BY-SA 4.0).

The anatomy description text embedded in `index.html` (names, descriptions,
functions, relations, clinical correlations) is also offered under CC BY-SA 4.0.

## Attribution

> 3D models: BodyParts3D © The Database Center for Life Science (CC BY-SA 2.1 Japan / v4.0 CC BY 4.0), via Z-Anatomy (CC BY-SA 4.0), and HuBMAP Human Reference Atlas (CC BY 4.0 — Kristen Browne, Heidi Schlehlein, Arie Kaufman / Stony Brook University), processed and packed for the web.

### Upstream per-part notices from `Z-Anatomy/License.txt`

- **BodyParts3D** — The Database Center for Life Science — CC-BY-SA 2.1 Japan (v4.0: CC BY 4.0)
- **Z-Anatomy** — The libre 3D atlas of anatomy — CC-BY-SA 4.0
- **Cranial Nerves and Foramina** — University of Dundee, CAHID — CC-BY 4.0
- **Anatomy of the Inner Ear** — University of Dundee School of Medicine — **CC-BY-NC-SA 4.0** *(non-commercial; audit auditory ossicles and cochlear/vestibular nerve meshes before any commercial use)*
- **Kidney** — Lissie Cowley — CC-BY-NC 4.0 *(no longer shipped in Human Atlas; replaced by HuBMAP CC BY 4.0 urinary models)*
- **Brainder** & **White matter** — University of Washington

## Full license text

Place the full legal code of CC BY-SA 4.0 in a file named `LICENSE` in this
folder (copy it from the "Read the Legal Code" link on the Creative Commons
page above).
