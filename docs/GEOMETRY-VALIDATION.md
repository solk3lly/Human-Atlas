# Human Atlas Geometry & Packing Validation Report

Generated directly from `tools/validate_geometry.py` against pinned HuBMAP `ccf-releases` commit `b036a91aaf7234f462b1249d4a5f4fb0e982f412` (all 12 source GLBs verified by SHA-256) and all 19 shipped `ha-mesh-v2` bundles.

See [docs/research/packing-and-geometry-validation.md](research/packing-and-geometry-validation.md) for the primary specifications, morphometry studies, and tolerance derivations.

## Validation Gates & Result

- **Status:** **PASS**
- **Encoding format:** `ha-mesh-v2` (`v: 2`, little-endian, 4-byte aligned `f32` / 2-byte aligned `u16`, `MAX_VERTICES = 65535` per WebGL 2.0 §5.14 / glTF 2.0 primitive-restart rules)
- **Tier 1 gates (source `float32` vs decoded):** `new_zero_area == 0`, `new_zero_normals == 0`, `max_disp <= 5.0 µm`, `p99_normal_err <= 1.0°`, `|ΔArea|/Area <= 0.05%`, closed-shell `|ΔVol|/Vol <= 0.05%` (gated strictly on watertight meshes; open surfaces preserved intact), exact topology preservation (`Δboundary = Δnonmanifold = Δcomponents = 0`), and byte-for-byte GLB reproducibility.
- **Tier 2 gates (landmarks & tubular sections):** branch/valve/UPJ/UVJ junction drift `<= 2.0 µm`, ureter perpendicular-to-centerline equivalent diameter ($D_{\text{eq}}$) drift `<= 5.0 µm`.

## Tier 1: Source-vs-Packed Fidelity Across All 6 HuBMAP Reference Layers

| Layer | Meshes (`u16` / `f32`) | Source Zero-Area | Packed Zero-Area | New Zero-Area | Max Disp (µm) | Max p99 Normal Err (°) | Byte-for-Byte Repro |
|---|---:|---:|---:|---:|---:|---:|:---:|
| `jantung` | 51 (48 / 3) | 203 | 203 | **0** | 1.849 | 0.177 | Yes |
| `urin` | 81 (78 / 3) | 0 | 0 | **0** | 1.990 | 0.320 | Yes |
| `limfa` | 7 (7 / 0) | 0 | 0 | **0** | 1.375 | 0.083 | Yes |
| `limfonodus` | 13 (13 / 0) | 0 | 0 | **0** | 0.176 | 0.403 | Yes |
| `ususHalus` | 10 (10 / 0) | 0 | 0 | **0** | 1.907 | 0.037 | Yes |
| `ususBesar` | 10 (10 / 0) | 0 | 0 | **0** | 2.769 | 0.029 | Yes |

### Key Thin/Problematic Meshes (Before Global `u16` vs After `ha-mesh-v2`)

| Layer / Mesh | Selected Encoding | Faces | Source Zero-Area | Old Global `u16` Zero-Area | New `ha-mesh-v2` Zero-Area | Max Vertex Disp (µm) | p99 Normal Err (°) | Surface Topology |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `jantung` / `Right_atrium.r` | `f32` | 47,299 | 184 | 2270 | **184** | 0.000 | 0.000 | Open (`b=121`) |
| `jantung` / `Left_coronary_artery.l` | `f32` | 12,233 | 6 | 8537 | **6** | 0.000 | 0.000 | Open (`b=369`) |
| `jantung` / `Superior_vena_cava` | `f32` | 11,212 | 13 | 122 | **13** | 0.000 | 0.000 | Open (`b=40`) |
| `urin` / `Kidney.l` | `u16` | 11,221 | 0 | 6 | **0** | 1.156 | 0.320 | Open (`b=38`) |
| `urin` / `Urinary_bladder` | `u16` | 112 | 0 | 2 | **0** | 0.136 | 0.006 | Open (`b=114`) |
| `urin` / `Urinary_bladder` | `u16` | 4,498 | 0 | 2 | **0** | 0.730 | 0.017 | Open (`b=248`) |
| `urin` / `Urinary_bladder` | `f32` | 4,888 | 0 | 2 | **0** | 0.000 | 0.000 | Open (`b=338`) |
| `urin` / `Prostatic_urethra` | `f32` | 3,309 | 0 | 158 | **0** | 0.000 | 0.000 | Open (`b=2057`) |
| `urin` / `Remaining_urethra` | `f32` | 1,655 | 0 | — | **0** | 0.000 | 0.000 | Open (`b=327`) |

## Tier 2: Named Landmarks, Branch Connectivity & Perpendicular-to-Centerline Sections

### Heart Branch, Ostial & Valve Junction Connectivity (`jantung`)

Normative coronary diameters for context: LMCA `4.5 ± 0.5 mm`, proximal LAD `3.7 ± 0.4 mm`, distal LAD `1.9 ± 0.4 mm`, proximal RCA `2.8–3.9 mm` (Dodge et al., *Circulation* 1992, PMID `1535570`; Medrano-Gracia et al., *EuroIntervention* 2016, PMID `27639736`). Valve cusp thicknesses `0.25–3.20 mm` (Sahasakul et al., *Am J Cardiol* 1988, PMID `3414519`).

| Landmark Pair | Source Min Dist (mm) | Packed Min Dist (mm) | Packing Drift (µm) |
|---|---:|---:|---:|
| `Ascending_aorta` ↔ `Left_coronary_artery.l` | 2.103 | 2.103 | 0.009 |
| `Ascending_aorta` ↔ `Right_coronary_artery.r` | 2.629 | 2.629 | 0.147 |
| `Left_coronary_artery.l` ↔ `Anterior_interventricular_artery` | 0.000 | 0.000 | 0.288 |
| `Left_coronary_artery.l` ↔ `Circumflex_artery_of_heart.l` | 0.000 | 0.000 | 0.092 |
| `Circumflex_artery_of_heart.l` ↔ `Left_marginal_artery.l` | 0.061 | 0.061 | 0.151 |
| `Anterior_interventricular_artery` ↔ `Diagonal_branches_of_lad_artery` | 0.000 | 0.000 | 0.231 |
| `Right_coronary_artery.r` ↔ `Posterior_interventricular_artery` | 0.000 | 0.000 | 0.136 |
| `Right_coronary_artery.r` ↔ `Right_marginal_artery.r` | 0.044 | 0.043 | 0.490 |
| `Superior_vena_cava` ↔ `Right_atrium.r` | 0.086 | 0.086 | 0.000 |
| `Inferior_vena_cava` ↔ `Right_atrium.r` | 0.052 | 0.052 | 0.276 |
| `Coronary_sinus` ↔ `Right_atrium.r` | 0.160 | 0.160 | 0.291 |
| `Coronary_sinus` ↔ `Great_cardiac_vein` | 0.012 | 0.013 | 0.399 |
| `Mitral_valve` ↔ `Left_ventricle.l` | 0.072 | 0.073 | 0.398 |
| `Tricuspid_valve` ↔ `Right_ventricle.r` | 0.134 | 0.133 | 0.203 |

### Urinary Junctions & Ureter Perpendicular-to-Centerline Calibre (`urin`)

Cross-sections are cut perpendicular to the local 3D centerline tangent (Antiga et al., VMTK 2008, PMID `19002516`) at arc-length stations measured distally from the **ureteropelvic junction (UPJ)** landmark. Exact contour loop chaining reveals that both HuBMAP ureter GLBs are **double-walled hollow tubes**, separating outer-wall $D_{\text{eq}}$ from inner-lumen $D_{\text{eq}}$ (~0.4–0.5 mm wall thickness). Clinical CT references differ by imaging protocol: unenhanced CT transverse diameter `1.8 ± 0.9 mm` (`96% ≤ 3 mm`, Zelenko et al., *AJR* 2004, PMID `15039184`) versus delayed contrast-enhanced CT `4.3–4.4 mm` (`95th pct 6.9 mm`, Itanyi et al., *Afr J Urol* 2020, DOI `10.1186/s12301-020-00021-0`). Horizontal axial slicing inflates oblique spans via $\sec\theta$ projection distortion.

| Junction | Source Min Dist (mm) | Packed Min Dist (mm) | Packing Drift (µm) |
|---|---:|---:|---:|
| `Renal_pelvis.l` ↔ `Ureter.l` | 0.031 | 0.031 | 0.315 |
| `Renal_pelvis.r` ↔ `Ureter.r` | 0.097 | 0.097 | 0.419 |
| `Ureter.l` ↔ `Ureteral_orifice.l` | 0.000 | 0.000 | 0.177 |
| `Ureter.r` ↔ `Ureteral_orifice.r` | 0.000 | 0.000 | 0.123 |
| `Urinary_bladder` ↔ `Prostatic_urethra` | 0.002 | 0.002 | 0.003 |

#### Left Ureter (`Ureter.l`) — Centerline Length `286.0 mm`

| Station (from UPJ) | Tilt (°) | Outer Minor × Major (mm) | Outer $D_{\text{eq}}$ (mm) | Inner Lumen $D_{\text{eq}}$ (mm) | Horiz. Major (mm) | Horiz. Inflation | Packing Drift (µm) |
|---|---:|---|---:|---:|---:|---:|---:|
| UPJ + 10 mm (`10.8`) | 36.7 | 3.76 × 4.29 | **4.01** | 2.99 | 5.25 | +31.1% | 0.271 |
| UPJ + 20 mm (`20.8`) | 27.2 | 3.73 × 3.99 | **3.85** | 2.83 | 4.49 | +16.8% | 0.126 |
| UPJ + 30 mm (`30.1`) | 23.9 | 3.60 × 3.93 | **3.73** | 2.72 | 4.22 | +13.1% | 0.105 |
| UPJ + 50 mm (`50.7`) | 21.3 | 3.56 × 4.01 | **3.75** | 2.73 | 4.22 | +12.6% | 0.105 |
| UPJ + 100 mm (`100.8`) | 7.6 | 3.83 × 3.97 | **3.90** | 2.89 | 3.98 | +2.0% | 0.017 |
| UPJ + 150 mm (`149.9`) | 16.9 | 4.42 × 4.53 | **4.45** | 3.44 | 4.81 | +7.9% | 0.216 |
| UPJ + 200 mm (`199.4`) | 40.0 | 4.26 × 4.59 | **4.38** | 3.38 | 5.82 | +32.7% | 0.163 |

#### Right Ureter (`Ureter.r`) — Centerline Length `244.7 mm`

| Station (from UPJ) | Tilt (°) | Outer Minor × Major (mm) | Outer $D_{\text{eq}}$ (mm) | Inner Lumen $D_{\text{eq}}$ (mm) | Horiz. Major (mm) | Horiz. Inflation | Packing Drift (µm) |
|---|---:|---|---:|---:|---:|---:|---:|
| UPJ + 10 mm (`10.3`) | 27.5 | 4.17 × 4.88 | **4.48** | 3.48 | 5.50 | +22.6% | 0.159 |
| UPJ + 20 mm (`20.6`) | 24.7 | 3.68 × 3.99 | **3.81** | 2.79 | 4.46 | +17.2% | 0.152 |
| UPJ + 30 mm (`30.7`) | 24.3 | 3.38 × 3.75 | **3.53** | 2.51 | 4.02 | +14.1% | 0.153 |
| UPJ + 50 mm (`50.7`) | 21.9 | 3.70 × 4.03 | **3.84** | 2.83 | 4.31 | +12.2% | 0.062 |
| UPJ + 100 mm (`100.3`) | 5.2 | 4.40 × 4.46 | **4.40** | 3.39 | 4.49 | +2.0% | 0.024 |
| UPJ + 150 mm (`150.4`) | 38.1 | 4.67 × 4.99 | **4.80** | 3.80 | 6.07 | +26.6% | 0.152 |
| UPJ + 200 mm (`200.5`) | 30.4 | 4.64 × 5.14 | **4.85** | 3.85 | 5.62 | +15.7% | 0.196 |

## Tier 3: Full 19-Layer Release Inventory (`ha-mesh-v2`)

| Layer | Source | Size (MiB) | Generation Hash | Meshes (`u16` / `f32`) | Triangles | Zero-Area Faces | Max Index |
|---|---|---:|---|---:|---:|---:|---:|
| `cerna` | Z-Anatomy / BP3D | 1.67 | `80e2446f06881e93` | 46 (46 / 0) | 153,853 | 0 | 11900 |
| `endo` | Z-Anatomy / BP3D | 0.36 | `04345bd3705e7e06` | 13 (13 / 0) | 31,206 | 0 | 4595 |
| `jantung` | HuBMAP HRA | 3.92 | `c9b4ec9a9e8b656d` | 51 (48 / 3) | 316,720 | 203 | 24065 |
| `limfa` | HuBMAP HRA | 0.23 | `9662fe330e1765cd` | 7 (7 / 0) | 19,602 | 0 | 3257 |
| `limfonodus` | HuBMAP HRA | 4.04 | `0b2bb541a361596b` | 13 (13 / 0) | 254,292 | 0 | 44193 |
| `organ` | Z-Anatomy / BP3D | 1.38 | `a021bb63d2e33d73` | 52 (52 / 0) | 127,221 | 0 | 14061 |
| `otot` | Z-Anatomy / BP3D | 9.76 | `aa6bee2670e69eec` | 462 (462 / 0) | 844,559 | 0 | 2767 |
| `rangka` | Z-Anatomy / BP3D | 3.79 | `9cd0ab29413e218c` | 277 (277 / 0) | 329,487 | 8 | 5870 |
| `repro` | Z-Anatomy / BP3D | 0.26 | `e79727b021fa82e4` | 15 (15 / 0) | 22,403 | 0 | 2459 |
| `saraf` | Z-Anatomy / BP3D | 1.04 | `01869cd240c3f8b5` | 237 (237 / 0) | 77,579 | 0 | 2845 |
| `urin` | HuBMAP HRA | 2.86 | `88c70c2601802cbb` | 81 (78 / 3) | 241,842 | 0 | 13544 |
| `ususBesar` | HuBMAP HRA | 0.40 | `45073bf4ce490cb9` | 10 (10 / 0) | 34,178 | 0 | 4501 |
| `ususHalus` | HuBMAP HRA | 0.39 | `0c3845fe933a59f9` | 10 (10 / 0) | 33,524 | 0 | 9906 |
| `vsAb` | Z-Anatomy / BP3D | 6.05 | `73e177694113b26c` | 112 (112 / 0) | 524,160 | 2 | 14447 |
| `vsKa` | Z-Anatomy / BP3D | 15.46 | `324d5a872372a669` | 162 (162 / 0) | 1,342,172 | 84 | 50529 |
| `vsKv` | Z-Anatomy / BP3D | 2.31 | `05ff9b9bf76ec562` | 59 (59 / 0) | 199,776 | 0 | 28385 |
| `vsLe` | Z-Anatomy / BP3D | 4.22 | `2503b46424c1d58c` | 80 (80 / 0) | 366,336 | 0 | 15671 |
| `vsTo` | Z-Anatomy / BP3D | 6.16 | `b3d5d7e41cd7549e` | 98 (98 / 0) | 534,528 | 0 | 31523 |
| `vsTu` | Z-Anatomy / BP3D | 6.19 | `a5cbc80b41e611b5` | 118 (118 / 0) | 536,256 | 0 | 12791 |
| **Total (19 layers)** | — | **70.48** | — | **1,903** | **5,989,694** | **297** | ≤ 65,534 |

### Summary of Precision Recovery & Anatomical Remediation
- **Total zero-area triangles across all 19 layers:** dropped from **11,336 → 297** (-97.4%), with **203** pre-existing zero-area faces in the unquantized HuBMAP source GLBs and **0** new zero-area triangles introduced by packing across all **172** HRA meshes.
- **Legacy `vsKa` (`Central_retinal_artery`):** restored from **230 → 98** zero-area faces by recovering the exact un-degraded `bc3f6f9` per-mesh quantization lattices (`4.28 µm` step vs `6.76 µm` regression) with zero extra binary payload.
- **HuBMAP HRA Phase A/B fixes (`tools/import_hra.py`):** split `Circumflex_artery_of_heart` (LCx) from upstream mislabeled `VH_M_diagonal_branch_of_left_anterior_descending_artery` (`FMA:3860`), restored all 5 previously dropped GLB nodes (`Renal_hilum.l/.r` in `urin`; `Duodenal_ampulla`, `Hepatopancreatic_ampulla_sphincter`, `Minor_duodenal_papilla` in `ususHalus`), removed within-mesh repeated triangles, and oriented all closed/nearly-closed shells to positive outward CCW winding.
- **Z-Anatomy Phase A/B fixes (`tools/repair_bundles.py`, `tools/rebuild_z_anatomy.py`):** stripped 12 coplanar `Diaphragm` origin stickers (`Diaphragm.o*`) from `organ` to eliminate z-fighting; rebuilt `otot` directly from Z-Anatomy `Startup.blend` (`4: Muscular system`) restoring **462** full 3D muscle bellies (replacing 80 enthesis-only bone stickers, resolving all 32 left/right swaps, fixing swapped Trapezius Ascending/Descending parts, and rescuing `Semitendinosus`, `Adductor*`, `Abductor*`, and `Tensor_fasciae_latae`); recovered contralateral `Transverse_sinus.r` (`vsKv`) and `Axillary_vein.l` (`vsLe`); relocated `Subcostal_artery` and `Inferior_phrenic_artery` from `vsTo` to `vsAb` and removed 3 orphaned Z-Anatomy coronary fragments from `vsTo`.
- **Release footprint:** total across all 19 `ha-mesh-v2` bundles is **70.48 MiB** (selective `f32` on 6 thin/sliver HRA meshes: `Right_atrium.r`, `Left_coronary_artery.l`, `Superior_vena_cava`, `Urinary_bladder`, `Prostatic_urethra`, `Remaining_urethra`).
