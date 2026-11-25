# 3D Mesh Packing Precision and Anatomical Geometry Validation: Primary-Source Research Report

> **Scope:** Primary-source technical and scientific foundations for the **Human Atlas** 3D web anatomy pipeline (Three.js r128 client, Python/NumPy offline packer in [`tools/import_hra.py`](../../tools/import_hra.py), HuBMAP Human Reference Atlas GLB v1.1/v1.2 reference organs, and BodyParts3D/Z-Anatomy legacy layers). Every normative requirement, equation, and anatomical tolerance is traced directly to its primary specification, source code, or peer-reviewed study.

---

## 1. 3D Mesh Quantization & Packing Precision

### 1.1 glTF 2.0 & WebGL 2.0 Normative Specifications

The Khronos **glTF 2.0 Specification** (ISO/IEC 12113:2022) defines the baseline geometric, numerical, and container conventions used by all HuBMAP HRA `.glb` inputs and WebGL/Three.js clients:

| Requirement | Normative Specification | Primary Source |
|---|---|---|
| **Coordinate system** | Right-handed Cartesian: `+Y` up, `+Z` front (anterior of an anatomical asset), `+X` asset's left. | [glTF 2.0 §Coordinate System and Units](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units) |
| **Physical units** | Linear distances in **metres (m)**; angles in **radians**; positive rotation is counter-clockwise; reference white point $D_{65}$. | [glTF 2.0 §Coordinate System and Units](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units) |
| **Byte order & GLBv2 layout** | Little-endian for all multi-byte values. 12-byte GLBv2 header (`uint32 magic = 0x46546C67` `"glTF"`, `uint32 version = 2`, `uint32 length`), followed by 4-byte-aligned chunks (`0x4E4F534A` `JSON` padded with `0x20`; `0x004E4942` `BIN\0` padded with `0x00`). | [glTF 2.0 §Binary glTF Layout](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#binary-gltf-layout), [§Chunk Structure (GLBv2)](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#chunks-v2) |
| **Buffer alignment** | `accessor.byteOffset` and `bufferView.byteOffset` MUST be multiples of component byte size. Vertex attribute elements MUST align to **4-byte boundaries** inside the buffer view (`accessor.byteOffset % 4 == 0`, and either component size is a multiple of 4 or `bufferView.byteStride` is a multiple of 4). | [glTF 2.0 §Accessing Data from Buffer Views](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#data-alignment) |
| **Accessor component types** | `FLOAT` (`5126`, 4-byte IEEE 754 `binary32`, `normalized: false`), `UNSIGNED_SHORT` (`5123`, 2-byte `uint16` or `unorm16` via $f = c/65535$), `UNSIGNED_INT` (`5125`, 4-byte `uint32`), `SHORT` (`5122`, `sint16`/`snorm16` via $f = \max(c, -32767)/32767$), `BYTE` (`5120`), `UNSIGNED_BYTE` (`5121`). | [glTF 2.0 §Accessor Data Types](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#accessor-data-types) |
| **Index primitive-restart prohibition** | Index accessors **MUST NOT** contain the maximum value of their component type: `255` (`uint8`), **`65535` (`uint16`)**, or `4294967295` (`uint32`). In WebGL 2.0, `PRIMITIVE_RESTART_FIXED_INDEX` is unconditionally enabled; index `65535` in a `Uint16Array` index buffer terminates and restarts the primitive instead of referencing vertex `65535`. | [glTF 2.0 §Topology and Connectivity](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#meshes-topology); [WebGL 2.0 §PRIMITIVE_RESTART_FIXED_INDEX is always enabled](https://registry.khronos.org/webgl/specs/latest/2.0/#5.14) |

> **Codebase Audit Finding:** [`tools/import_hra.py`](../../tools/import_hra.py) sets `MAX_VERTICES = 65536` and packs face indices as little-endian `uint16`. Because Three.js r128 creates a WebGL 2 context by default, any chunk with 65,536 vertices emits vertex index `65535` (`0xFFFF`), violating both glTF 2.0 and WebGL 2.0 and silently dropping/corrupting incident triangles. `MAX_VERTICES` for `uint16` indices must be at most **`65535`** (maximum index `65534`, `0xFFFE`).

### 1.2 `KHR_mesh_quantization`, Draco, and `meshoptimizer` Quantization Principles

Three primary standards and reference implementations define production mesh quantization:

1. **Khronos `KHR_mesh_quantization` (ratified glTF 2.0 extension):**
   - Extends `POSITION` (`VEC3`) beyond `FLOAT` to signed/unsigned 8-bit or 16-bit integers (`BYTE`, `UNSIGNED_BYTE`, `SHORT`, `UNSIGNED_SHORT`), normalized or unnormalized, and extends `NORMAL` (`VEC3`) strictly to **signed normalized** `BYTE` or `SHORT` (`normalized: true`), aligned to 4-byte strides (e.g., 4 bytes per `BYTE` normal, 8 bytes per `SHORT` position).
   - Dequantization is encoded via standard `node` scale/translation (or `inverseBindMatrices` for skinned meshes). The specification explicitly recommends **uniform XYZ scale** to avoid skewing normals, notes that unnormalized integers avoid exact-representability loss of `1/65535` in binary floating point, and documents the core granularity trade-off:
     - **Per-mesh AABB quantization** minimizes quantization error for each individual mesh, *but* can quantize shared boundary vertices onto different lattices, creating **visible cracks/seams** between adjacent meshes.
     - **Scene/layer-global AABB quantization** eliminates inter-mesh cracks, *but* inflates quantization error on small structures.
   - *Primary source:* [KhronosGroup/glTF `KHR_mesh_quantization` README](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_mesh_quantization/README.md).

2. **Google Draco (`AttributeQuantizationTransform`):**
   - Computes per-attribute bounding box `min_values_[c]` and **isotropic** scalar range `range_ = max_c (max_values_[c] - min_values_[c])`, quantizing into $[0, 2^b - 1]$ ($1 \le b \le 30$) via nearest-integer rounding `floor((val - min_c) / delta + 0.5f)` where $\Delta = \text{range} / (2^b - 1)$.
   - Supports overriding origin and range (`SetParameters`) so abutting sub-meshes can share one lattice without cracking.
   - *Primary source:* [google/draco `attribute_quantization_transform.cc`](https://github.com/google/draco/blob/main/src/draco/attributes/attribute_quantization_transform.cc) and [`quantization_utils.h`](https://github.com/google/draco/blob/main/src/draco/core/quantization_utils.h).

3. **`meshoptimizer` & `gltfpack`:**
   - Provides `meshopt_quantizeUnorm`, `meshopt_quantizeSnorm`, and `meshopt_quantizeHalf`, targeting GPU-ready quantized vertex streams (`KHR_mesh_quantization`, supported in Three.js r111+) optionally supercompressed with `EXT_meshopt_compression` (supported in Three.js r122+) + HTTP gzip/Brotli.
   - Recommends running quantization *after* geometric processing (simplification, normal computation) because earlier stages require `float32` positions; offers `-vpf` (floating-point position storage without node dequantization transforms) when exact coordinates or crack-free joins are critical, and `-kn`/`-ke` to preserve named anatomical nodes and `extras` metadata.
   - *Primary source:* [zeux/meshoptimizer `README.md`](https://github.com/zeux/meshoptimizer/blob/master/README.md) and [`gltf/README.md`](https://github.com/zeux/meshoptimizer/blob/master/gltf/README.md).

### 1.3 Quantization Error Bounds and Encoding Scheme Comparison

For a uniform $b$-bit unsigned lattice over span $S$ with grid step $\Delta = S / (2^b - 1)$ (for $b=16$, $\Delta = S / 65535$), nearest-integer rounding bounds per-axis coordinate error to $|e_k| \le \Delta / 2$. Under the standard independent uniform quantization noise model $e_k \sim \mathcal{U}(-\Delta/2, +\Delta/2)$:

$$\begin{aligned}
\|e\|_{\infty} &\le \frac{\Delta}{2}, \qquad
\|e\|_{2,\max} = \frac{\sqrt{3}}{2}\,\Delta \approx 0.8660\,\Delta, \qquad
\text{RMS}_{3\text{D}} = \sqrt{3 \cdot \frac{\Delta^2}{12}} = \frac{\Delta}{2}, \\
|\Delta D_{\max}| &= 2\|e\|_{2,\max} = \sqrt{3}\,\Delta \approx 1.7321\,\Delta \quad (\text{worst-case diameter/thickness distortion}).
\end{aligned}$$

For **IEEE 754 `binary32` (`float32`)**, the 24-bit significand (23 explicit + 1 implicit bit) gives machine epsilon $\varepsilon = 2^{-23} \approx 1.192 \times 10^{-7}$ and unit-in-the-last-place spacing $\text{ULP}(x) = 2^{\lfloor \log_2 |x| \rfloor - 23}$: at $|x| \in [0.5, 1.0)\,\text{m}$, $\text{ULP} = 5.96 \times 10^{-8}\,\text{m} = 0.060\,\mu\text{m}$ (max rounding error $0.030\,\mu\text{m}$); at $|x| \in [1.0, 2.0)\,\text{m}$, $\text{ULP} = 0.119\,\mu\text{m}$ (max error $0.060\,\mu\text{m}$).

| Encoding Scheme | Bytes / Vertex (`POS`) | Grid Step $\Delta$ | Max 3D Displacement | Inter-Mesh Seam Behavior | Normal / Transform Impact |
|---|---|---|---|---|---|
| **Layer-global isotropic `uint16`** *(current Human Atlas)* | 6 B (+33% Base64 = 8 B) | $S_{\text{layer}} / 65535$ | $0.866\,S_{\text{layer}} / 65535$ | Crack-free within layer | Severe precision loss on small structures when $S_{\text{layer}} \gg S_{\text{mesh}}$. |
| **Per-mesh local isotropic `uint16`** | 6 B (+16 B header/mesh) | $S_{\text{mesh}} / 65535$ | $0.866\,S_{\text{mesh}} / 65535$ | May crack at shared mesh boundaries unless adjacent meshes share a cluster AABB | Uniform scale preserves normal directions (`KHR_mesh_quantization` recommended). |
| **Per-mesh local anisotropic `uint16`** | 6 B (+24 B header/mesh) | $\Delta_k = (hi_k - lo_k)/65535$ | $\frac{1}{2}\sqrt{\Delta_x^2+\Delta_y^2+\Delta_z^2}$ | Cracks across meshes; non-uniform error along elongated vessels | Non-uniform node scale distorts normals unless dequantized to world space before normal calculation or inverse-transpose normal matrix applied. |
| **IEEE 754 `float32`** *(native GLB / binary)* | 12 B (raw); ~4–6 B with meshopt + gzip/Brotli | $\text{ULP}(x) \le 0.12\,\mu\text{m}$ at $2\,\text{m}$ | $\le 0.06\,\mu\text{m}$ (lossless vs GLB `FLOAT`) | Exact seam preservation | Exact fidelity; zero quantization-induced triangle collapse. |

### 1.4 Degenerate Triangle Collapse and Client Normal Corruption (`computeVertexNormals()`)

Human Atlas does **not** ship vertex normals; instead, [`index.html`](../../index.html) dequantizes positions into `Float32Array` and runs `BufferGeometry.computeVertexNormals()` in Three.js r128. Inspection of Three.js r128 primary source ([`src/core/BufferGeometry.js`](https://github.com/mrdoob/three.js/blob/r128/src/core/BufferGeometry.js) and [`src/math/Vector3.js`](https://github.com/mrdoob/three.js/blob/r128/src/math/Vector3.js)) confirms the exact mechanism:

1. **Area-weighted accumulation:** For each triangle $(v_A, v_B, v_C)$, Three.js computes `cb = pC - pB`, `ab = pA - pB`, and accumulates `cb.cross(ab)` (magnitude $2 \times \text{Area}(\triangle)$) onto all three incident vertices.
2. **Zero-vector fallback:** `normalizeNormals()` calls `Vector3.normalize()`, implemented in r128 as `this.divideScalar( this.length() || 1 )`. If all triangles incident to a vertex collapse to zero area, the accumulated normal remains `(0, 0, 0)` (unlit/black shading in PBR/Lambertian lighting, and undefined/NaN if normalized in custom GLSL).
3. **Two failure modes under coarse quantization:**
   - **Triangle collapse ($\text{Area} = 0$):** Occurs whenever an edge length $\ell < \Delta$ snaps two vertices to the same lattice node, or three quantized vertices become collinear on the integer grid.
   - **Normal tilting & inversion (staircasing):** For a non-degenerate triangle with minimum altitude $h = 2A / \ell_{\max}$, vertex perturbations up to $\delta_v = \frac{\sqrt{3}}{2}\Delta$ tilt the face normal by up to $\delta\theta \approx \arcsin\!\big(\min(1, \sqrt{3}\Delta / h)\big)$ (reaching $\sim 10^\circ$ at $h \approx 10\Delta$, and risking **normal flipping / triangle inversion** of $180^\circ$ whenever $h \lesssim \sqrt{3}\Delta$). Because Three.js r128 accumulates area-weighted cross products directly from quantized positions, thin tubes (coronary and retinal vessels) and finely tessellated thin sheets suffer visible faceted shading and zero-normal creases.

### 1.5 Mixed-Scale Layer Trade-offs: Empirical Audit of Shipped Human Atlas Bundles

Mixing millimetre- and sub-millimetre structures with decimetre- to metre-scale organs in one global 16-bit bounding box produces scale dynamic ranges of **17× to 420×** across the currently shipped `data/atlas_*.json` bundles:

| Layer Bundle | Global Scale $S_{\text{layer}}$ | Global Step $\Delta_{\text{global}}$ | Max Vertex Disp. | Smallest Critical Structure (Max Extent) | Scale Ratio $S_{\text{layer}}/S_{\text{mesh}}$ | Per-Mesh Local $\Delta_{\text{local}}$ | Observed Degenerate Faces / Zero-Normal Vertices in Shipped Bundle |
|---|---|---|---|---|---|---|---|
| `atlas_jantung.json` | `0.5142 m` | `7.85 µm` | `6.80 µm` | `Left_coronary_artery.l` (`13.32 mm`) | **38.6×** | `0.203 µm` | **8,523 / 12,240** faces (69.6%); **3,155 / 6,306** zero-normal verts *(layer total: 10,915 zero-area faces, 4,332 zero-normal verts; 6,306 → 1,615 unique quantized points)* |
| `atlas_vsKa.json` | `0.4427 m` | `6.76 µm` | `5.85 µm` | `Central_retinal_artery` (`17.45–33.31 mm`) | **13.3–25.4×** | `0.266–0.508 µm` | **230** zero-area faces, **3** zero-normal verts across CRA chunks; worst-case diameter error (`11.7 µm`) is **7.2–8.1%** of physiological CRA lumen (`144–163 µm`) |
| `atlas_urin.json` | `0.4654 m` | `7.10 µm` | `6.15 µm` | `Ureteral_orifice` (`10.04 mm`), `Prostatic_urethra` (`21.27 mm`) | **21.9–46.4×** | `0.153–0.325 µm` | `Prostatic_urethra`: **155 / 3,309** faces (4.7%), **45** zero-normal verts *(layer total: 163 zero-area faces, 45 zero-normal verts)* |
| `atlas_rangka.json` | `1.6962 m` | `25.88 µm` | `22.41 µm` | `Stapes` (`4.04 mm`), `Malleus` (`8.10 mm`) | **209–420×** | `0.062–0.124 µm` | `Stapes.l/r`, `Malleus.l`: **8** zero-area faces, **2** zero-normal verts |
| `atlas_limfonodus.json` | `0.0183 m` | `0.28 µm` | `0.24 µm` | `Afferent_lymphatic_vessels` (`9.51 mm`) | **1.9×** | `0.145 µm` | **0** zero-area faces *(well-matched scale; 324 zero-normal verts stem from unreferenced/open source vertices)* |

> **Diagnostic Note:** For `Left_coronary_artery.l`, inspecting the packed bundle alone cannot separate pre-existing sub-`7.85 µm` edges or duplicate vertices in `VH_M_Heart.glb` from pure quantization collapse; however, the mesh uses only `653–1,698` of `65,535` integer steps (1.0%–2.6% of dynamic range). Diffing every packed mesh directly against its unquantized `float32` source GLB is mandatory to isolate encoding loss from upstream mesh artifacts.

---

## 2. Anatomical 3D Mesh Validation & Reference Benchmarks

### 2.1 *Metrics Reloaded* Framework for Biomedical 3D Geometry

**Maier-Hein et al. (2024)** (*Nature Methods* 21:195–212, DOI: [10.1038/s41592-023-02151-z](https://doi.org/10.1038/s41592-023-02151-z), PMID: `38347141`, PMCID: [PMC11182665](https://pmc.ncbi.nlm.nih.gov/articles/PMC11182665/)) and its companion pitfall taxonomy **Reinke et al. (2024)** (*Nature Methods* 21:182–194, DOI: [10.1038/s41592-023-02150-0](https://doi.org/10.1038/s41592-023-02150-0), PMID: `38347140`, PMCID: [PMC11181963](https://pmc.ncbi.nlm.nih.gov/articles/PMC11181963/)) establish a consensus *problem-fingerprint* methodology for validating biomedical spatial geometry:

- **Pitfalls of overlap metrics (DSC/IoU) on small & complex structures:** Reinke et al. ([P2.2]) show that overlap metrics suffer severe size sensitivity (a single-step boundary shift catastrophically alters DSC on small vessels/ossicles while barely moving DSC on large organs), are **shape-unaware** (missing fine vessel branches is invisible to DSC), and mask small-structure errors when aggregated across mixed-scale organs ([P3.2]).
- **Complementary boundary-distance metrics (Subprocess S7):** *Metrics Reloaded* recommends pairing overlap/topological checks with physical surface-distance metrics (in mm or µm), originally formalized for triangulated surfaces via dense surface sampling in **Cignoni, Rocchini & Scopigno (1998)** (*Metro*, *Computer Graphics Forum* 17(2):167–174, DOI: [10.1111/1467-8659.00236](https://doi.org/10.1111/1467-8659.00236)):
  - **Hausdorff Distance ($\text{HD}$):** $\max\!\big(\sup_{a \in A} d(a, B),\; \sup_{b \in B} d(b, A)\big)$ — captures worst-case spatial error; essential for deterministic packing/quantization verification (where vertex correspondence reduces this to exact $L_\infty$ displacement), but hypersensitive to isolated outliers in cross-atlas comparisons (Reinke [P2.3]).
  - **95th-Percentile Hausdorff Distance ($\text{HD}_{95}$):** Robust against single-vertex/annotation outliers when comparing derived meshes against external clinical or HRA reference models.
  - **Average Symmetric Surface Distance ($\text{ASSD}$):** Mean bidirectional point-to-surface distance across surfaces $A$ and $B$; measures global contour fidelity. Note Reinke [P3.1]: implementations vary in boundary sampling/extraction, so validation suites MUST pin one exact surface-sampling definition (e.g., area-weighted Monte Carlo / barycentric triangle sampling, not vertex-only point clouds).
  - **Normalized Surface Distance ($\text{NSD}$, Surface Dice at tolerance $\tau$):** Fraction of boundary surface within a clinically grounded tolerance $\tau$ (recommended default in *Metrics Reloaded* when reference boundaries carry known biological or segmentation uncertainty).
- **Tubular & topological metrics (Subprocess S6):**
  - **Centerline Dice (`clDice`)** — **Shit et al. (2021)** (*CVPR 2021*, DOI: [10.1109/cvpr46437.2021.01629](https://doi.org/10.1109/cvpr46437.2021.01629)) — evaluates topological connectivity and branch preservation of tubular networks (coronaries, retinal trees, ureters, lymphatics) where volumetric overlap fails.
  - **Discrete topological invariants:** Connected components ($\beta_0$), boundary loops ($b$), and Euler characteristic $\chi = V - E + F = 2\beta_0 - 2g - b$ (for orientable 2-manifolds with boundary) detect accidental vertex welding, hole creation, or component fragmentation caused by quantization or decimation.
- **Volume error & intentionally open anatomical surfaces:**
  - Closed-shell signed volume $V = \frac{1}{6}\sum_t (v_{t0} \times v_{t1}) \cdot v_{t2}$ is mathematically valid **only for watertight, consistently oriented closed shells** (zero boundary edges: every half-edge paired).
  - Many anatomical reference meshes are **intentionally open surfaces** (transected vascular ostia, cardiac chambers open at valve annuli, thin cardiac valve leaflets, pleural/peritoneal sheets, open renal calyces). Applying closed-volume error or automatic hole-filling to such meshes is scientifically invalid; validation must instead assert **boundary-edge & loop preservation** ($\Delta b = 0$, preserved ostial perimeter/diameter).

### 2.2 HuBMAP Human Reference Atlas (HRA) 3D Reference Object Library

Primary publications and SOPs governing the HuBMAP HRA assets imported by [`tools/import_hra.py`](../../tools/import_hra.py):

- **Foundational Architecture:** **Börner et al. (2021)**, *"Anatomical structures, cell types and biomarkers of the Human Reference Atlas"*, *Nature Cell Biology* 23:1117–1128, DOI: [10.1038/s41556-021-00788-6](https://doi.org/10.1038/s41556-021-00788-6), PMID: `34750582`, PMCID: [PMC10079270](https://pmc.ncbi.nlm.nih.gov/articles/PMC10079270/).
- **Spatial & Ontology Specification (HRA v1.2):** **Herr et al. (2023)** (senior author K. Börner), *"Specimen, biological structure, and spatial ontologies in support of a Human Reference Atlas"*, *Scientific Data* 10:171, DOI: [10.1038/s41597-023-01993-8](https://doi.org/10.1038/s41597-023-01993-8), PMID: `36973309`, PMCID: [PMC10043028](https://pmc.ncbi.nlm.nih.gov/articles/PMC10043028/). Introduces CCF Ontology v2.0.1 covering 26 organs in HRA v1.2, linking UBERON/FMA anatomical structures to `Spatial Object Reference` `.glb` files and `Spatial Placement` transforms (position, dimensions, rotation in HRA coordinate space).
- **Blood Vasculature Database (HRA-VCCF):** **Boppana et al. (2023)** (with K. Börner & G. Weber), *"Anatomical structures, cell types, and biomarkers of the healthy human blood vasculature"*, *Scientific Data* 10:452, DOI: [10.1038/s41597-023-02018-0](https://doi.org/10.1038/s41597-023-02018-0), PMID: `37468503`, PMCID: [PMC10356915](https://pmc.ncbi.nlm.nih.gov/articles/PMC10356915/) (993 vessels, branching topology, geometric properties, links to 3D reference objects).
- **Approval & Publication SOPs (Zenodo):**
  - Quardokus, Bueckle, Börner, Record & Browne (2022), *SOP: 3D Reference Object Approval* (v2.2.0), DOI: [10.5281/zenodo.5944197](https://doi.org/10.5281/zenodo.5944197) — documents medical illustrator authoring and organ Subject Matter Expert (SME) review.
  - Quardokus, Schlehlein & Bueckle (2023), *SOP: Adding 3D Reference Objects to the Human Reference Atlas* (v1.2.0), DOI: [10.5281/zenodo.10358858](https://doi.org/10.5281/zenodo.10358858) (concept DOI: [10.5281/zenodo.5639651](https://doi.org/10.5281/zenodo.5639651)) — documents `ccf-releases` publishing and portal integration.

#### Provenance Registry of `ccf-releases` v1.1 / v1.2 Models Used in Human Atlas

All records below are verified directly from [`hubmapconsortium/ccf-releases`](https://github.com/hubmapconsortium/ccf-releases) (`CC BY 4.0`, NIH Award `OT2OD026671`):

| Release & File | HuBMAP ID / DOI | Creators / SME Reviewer | Source & Model Construction Notes |
|---|---|---|---|
| `v1.1/VH_M_Heart.glb` | `HBM548.CTHS.699` / [10.48539/HBM548.CTHS.699](https://doi.org/10.48539/HBM548.CTHS.699) | K. Browne / S. Lin | NLM Visible Human Male (2021-12-01). Includes valves, septum, SVC, coronaries. *(Note: citation text in upstream `.md` has typo "Female" despite Male GLB).* |
| `v1.2/VH_M_Kidney_L.glb` | `HBM562.JGPS.244` / [10.48539/HBM562.JGPS.244](https://doi.org/10.48539/HBM562.JGPS.244) | K. Browne, H. Schlehlein / J. Spraggins, S. Jain | VHM (2022-05-06). Calyces/papillae moved to ureter model per SME input. |
| `v1.2/VH_M_Kidney_R.glb` | `HBM272.ZVPQ.979` / [10.48539/HBM272.ZVPQ.979](https://doi.org/10.48539/HBM272.ZVPQ.979) | K. Browne, H. Schlehlein / J. Spraggins, S. Jain | VHM (2022-05-06). Same boundary reassignment to ureter model. |
| `v1.2/VH_M_Ureter_L.glb` | `HBM473.XWNL.438` / [10.48539/HBM473.XWNL.438](https://doi.org/10.48539/HBM473.XWNL.438) | K. Browne, H. Schlehlein / D. Strand | VHM (2022-05-06). Includes renal pelvis, major/minor calyces, and papillae. |
| `v1.2/VH_M_Ureter_R.glb` | `HBM878.DBSR.759` / [10.48539/HBM878.DBSR.759](https://doi.org/10.48539/HBM878.DBSR.759) | K. Browne, H. Schlehlein / D. Strand | VHM (2022-05-06). Same as left ureter. |
| `v1.2/VH_M_Urinary_Bladder.glb` | `HBM934.DMHJ.898` / [10.48539/HBM934.DMHJ.898](https://doi.org/10.48539/HBM934.DMHJ.898) | K. Browne, H. Schlehlein / D. Strand | VHM (2022-05-06). Contains trigone and bilateral `ureteral_orifice` meshes. |
| `v1.2/VH_M_Urethra.glb` | Mapped in `v1.2/models/ASCT-B_3D_Models_Mapping.csv` | HuBMAP HRA Team | Maps `VH_M_urethra` (`UBERON:0001333`), `VH_M_prostatic_urethra` (`UBERON:0001335`), and `VH_M_other_urethra`. |
| `v1.2/VH_M_Spleen.glb` | `HBM662.GMWC.569` / [10.48539/HBM662.GMWC.569](https://doi.org/10.48539/HBM662.GMWC.569) | K. Browne, H. Schlehlein / M. Jorgensen | VHM (2022-05-06). Partitioned into visceral surfaces (`FMA:15828/15837/15838/15839`) and hilum (`UBERON:0001248`). |
| `v1.2/VH_M_Thymus.glb` | `HBM823.SNLN.667` / [10.48539/HBM823.SNLN.667](https://doi.org/10.48539/HBM823.SNLN.667) | K. Browne, H. Schlehlein / M. Brusko | VHM (2022-05-06). Left (`UBERON:0005457`) and right (`UBERON:0005469`) lobes. |
| `v1.2/NIH_M_Lymph_Node.glb` | `HBM299.VVXH.634` / [10.48539/HBM299.VVXH.634](https://doi.org/10.48539/HBM299.VVXH.634) | K. Browne / M. Jorgensen | Representative micro-organ scale (~18.3 mm); nodes prefixed `Yao_*` (`UBERON:0002509` et al.). |
| `v1.2/VH_M_Small_Intestine.glb` | `HBM468.FFTJ.536` / [10.48539/HBM468.FFTJ.536](https://doi.org/10.48539/HBM468.FFTJ.536) | K. Browne, H. Schlehlein / M. Arends | VHM (2022-05-06). Total centerline length `285 cm`; embeds centerline measurement markers (1 cm/5 cm/jejunoileal junction). |
| `v1.2/SBU_M_Intestine_Large.glb` | `HBM334.LVTH.937` / [10.48539/HBM334.LVTH.937](https://doi.org/10.48539/HBM334.LVTH.937) | K. Browne, H. Schlehlein / Y. Lin | Stony Brook Univ. base data (A. Kaufman) sculpted as custom ZBrush reference mesh — **not** a raw VHM segmentation; account for artistic sculpting when setting shape tolerances. |

### 2.3 Primary Anatomical Morphometry Benchmarks for Thin & Tubular Structures

Physically grounded quantization and geometric validation tolerances must scale to the true physiological dimensions of the smallest structures in each layer:

#### A. Normal Human Coronary Arteries & Cardiac Valve Leaflets
- **Dodge et al. (1992)** — *Circulation* 86(1):232–246, DOI: [10.1161/01.cir.86.1.232](https://doi.org/10.1161/01.cir.86.1.232), PMID: `1535570` (quantitative coronary arteriography of 83 angiographically normal subjects selected from 9,160 studies; 96 anatomical points across 32 segments; repeat measurement error `0.12 mm`):
  - **LMCA:** `4.5 ± 0.5 mm`
  - **Proximal LAD:** `3.7 ± 0.4 mm`; **Distal LAD:** `1.9 ± 0.4 mm`
  - **Proximal RCA:** `3.9 ± 0.6 mm` (right-dominant) vs. `2.8 ± 0.5 mm` (left-dominant; $p < 0.01$)
  - **Proximal LCX:** `3.4 ± 0.5 mm` (right-dominant) vs. `4.2 ± 0.6 mm` (left-dominant; $p < 0.01$)
  - **Sex effect:** Women have `-9%` smaller epicardial lumen diameters than men ($p < 0.001$), persisting after BSA normalization ($p < 0.01$).
- **Medrano-Gracia et al. (2016)** — *EuroIntervention* 12(7):845–854, DOI: [10.4244/EIJV12I7A139](https://doi.org/10.4244/EIJV12I7A139), PMID: `27639736` (3D CTA centerline/luminal computational atlas of 300 adults with zero calcium score and no stenosis): **LMCA** lumen `3.5 ± 0.8 mm` (length `10.5 ± 5.3 mm`), establishing contemporary 3D CTA normative ranges for bifurcations (LAD/diagonal, LCX/obtuse marginal, RCA crux).
- **Sahasakul et al. (1988)** — *Am J Cardiol* 62(7):424–430, DOI: [10.1016/0002-9149(88)90971-x](https://doi.org/10.1016/0002-9149(88)90971-x), PMID: `3414519` (autopsy morphometry of 200 normal human hearts):
  - **Aortic cusp nodule:** `0.67 mm` (<20 yr), `0.87 mm` (20–59 yr), `1.42 mm` ($\ge$60 yr); closing edge is ~half as thick as the nodule ($p < 0.001$), and the middle cusp belly is $\ge$25% thinner still (`~0.25–0.50 mm`).
  - **Mitral leaflets:** Anterior `1.30 / 1.60 / 3.20 mm`; posterior `0.91 / 1.13 / 2.04 mm` across the same age groups.
  - *Implication:* Thin valve leaflets (`0.25–1.5 mm`) and distal coronary branches (`~1.5–1.9 mm`) require sub-`5–10 µm` encoding error and strict preservation of open-sheet geometry.

#### B. Human Central Retinal Artery (CRA) & Retinal Arterioles
- **Dorner et al. (2002)** — *Curr Eye Res* 25(6):341–345, DOI: [10.1076/ceyr.25.6.341.14231](https://doi.org/10.1076/ceyr.25.6.341.14231), PMID: `12789540` (combined laser Doppler velocimetry, Zeiss RVA, and color Doppler imaging in 24 healthy young men): calculated **mean CRA trunk diameter = `163 ± 17 µm`**, matching *in vitro* histological values.
- **Knudtson et al. (2003)** — *Curr Eye Res* 27(3):143–149, DOI: [10.1076/ceyr.27.3.143.16049](https://doi.org/10.1076/ceyr.27.3.143.16049), PMID: `14562179`: established scale- and vessel-count-independent **revised CRAE** formulas summarizing the 6 largest retinal arterioles in the 0.5–1.0 disc-diameter ring (validated across 4,926 Beaver Dam Eye Study participants).
- **Wong et al. (2006)** — *Invest Ophthalmol Vis Sci* 47(6):2341–2350, PMID: `16723443` (Multi-Ethnic Study of Atherosclerosis, $n = 5{,}979$, ages 45–84): **mean adult CRAE = `144.1 ± 14.4 µm`** (CRVE `214.0 ± 22.2 µm`). **Yip et al. (2016)** (*Transl Vis Sci Technol* 5(5):11, PMID: `27752402`) further quantify cross-platform measurement offsets (`6.7–21.8 µm`), underscoring that **micrometre-scale steps are physiologically meaningful**.
- **Kocabiyik et al. (2005)** — *Ophthalmic Physiol Opt* 25(4):375–378, DOI: [10.1111/j.1475-1313.2005.00286.x](https://doi.org/10.1111/j.1475-1313.2005.00286.x), PMID: `15953124` (30 human orbits): CRA penetrates the optic nerve `6.4–15.2 mm` posterior to the globe.
- *Implication:* At `144–163 µm` physiological calibre, a `6.76 µm` global grid step (`atlas_vsKa.json`, worst-case diameter distortion `11.7 µm`) equals **7.2%–8.1% of the entire CRA diameter** and **~35%–40% of population SD**. Packing retinal arteries on a local `uint16` AABB (`~0.39 µm` step) or `float32` brings encoding error below **0.3%** of lumen diameter.

#### C. Normal Human Ureter Calibre & Perpendicular-to-Centerline Protocols
- **Zelenko et al. (2004)** — *AJR Am J Roentgenol* 182(4):1039–1041, DOI: [10.2214/ajr.182.4.1821039](https://doi.org/10.2214/ajr.182.4.1821039), PMID: `15039184`: retrospective unenhanced helical CT of 212 consecutive patients; measured largest transverse dimension on the asymptomatic non-obstructed ureter **starting 1–2 cm below the ureteropelvic junction (UPJ)**. Mean **`1.8 ± 0.9 mm`**; 96% of normal ureters were **`≤ 3 mm`** (establishing **3 mm** as upper limit of normal on unenhanced CT; obstructed mean `7.0 ± 3.2 mm`).
- **Itanyi et al. (2020)** — *African Journal of Urology* 26(1), DOI: [10.1186/s12301-020-00021-0](https://doi.org/10.1186/s12301-020-00021-0): contrast-enhanced delayed-phase helical CT of 170 adults (340 ureters), largest transverse dimension beginning 1–2 cm below the UPJ. Mean left **`4.3 mm`** (range `1.7–8.0 mm`), right **`4.4 mm`** (range `1.5–8.0 mm`), 95th percentile **`6.9 mm`** (upper limit **`7 mm`** under contrast opacification/diuretic distension; no significant age/sex difference).
- **Why perpendicular-to-centerline cross-sections differ from horizontal Z-slices:**
  - As formalized in **Antiga et al. (2008)** (Vascular Modeling Toolkit / VMTK, *Med Biol Eng Comput* 46(11):1097–1112, DOI: [10.1007/s11517-008-0420-1](https://doi.org/10.1007/s11517-008-0420-1), PMID: `19002516`), objective tubular morphometry extracts a 3D centerline $\mathbf{c}(s)$ (medial axis / maximal inscribed spheres) and slices the mesh with planes orthogonal to the unit tangent $\hat{\mathbf{t}}(s) = \mathbf{c}'(s)/\|\mathbf{c}'(s)\|$.
  - Slicing a tube of true diameter $D$ inclined by angle $\theta$ from the vertical $Z$-axis with a horizontal axial plane cuts an ellipse whose major axis is inflated by $\sec\theta$:
    $$D_{\text{axial}} = \frac{D}{\cos\theta}$$
    At $\theta = 30^\circ$, axial width inflates by `+15.5%`; at $\theta = 45^\circ$, `+41.4%`; at $\theta = 60^\circ$, `+100%`. Near the **UPJ** (flaring into the renal pelvis), at the **pelvic brim / iliac vessel crossing**, and along the curved **pelvic ureter** turning anteriorly/medially toward the **ureterovesical junction (UVJ)**, horizontal Z-slices conflate obliquity and funnel flare with true calibre. Automated validation MUST therefore measure equivalent circular diameter $D_{\text{eq}}(s) = 2\sqrt{A_\perp(s)/\pi}$ and maximal inscribed diameter $2r_{\text{MIS}}(s)$ in planes perpendicular to $\hat{\mathbf{t}}(s)$ at named arc-length landmarks (e.g., `15–20 mm` distal to UPJ, mid-abdominal segment, pelvic brim, and `10 mm` proximal to UVJ).

### 2.4 DICOM Image Plane Module (PS3.3 Section C.7.6.2)

For any mesh reconstructed from clinical CT/MR or Visible Human cross-sections, physical scale and anatomical orientation originate from **DICOM PS3.3 Section C.7.6.2 (Image Plane Module)** ([official NEMA standard](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.7.6.2.html)):

- **Reference Coordinate System (RCS):** Patient-based right-handed **LPS** frame in **millimetres (mm)**: `+X` = Patient's Left, `+Y` = Patient's Posterior, `+Z` = Patient's Superior (Head).
- **Mandatory Spatial Attributes (Table C.7-10):**
  - `Pixel Spacing` `(0028,0030)` (Type 1): physical center-to-center spacing `[row_spacing \ column_spacing]` in mm ($\Delta_r, \Delta_c$).
  - `Image Orientation (Patient)` `(0020,0037)` (Type 1): six direction cosines $[X_x, X_y, X_z, Y_x, Y_y, Y_z]$ of the first row and first column relative to LPS.
  - `Image Position (Patient)` `(0020,0032)` (Type 1): LPS coordinates $[S_x, S_y, S_z]$ (mm) of the center of the upper-left voxel `(0, 0)`.
  - `Slice Thickness` `(0018,0050)` (Type 2) and `Slice Location` `(0020,1041)` (Type 3).
- **Pixel-to-Patient Affine Transform (PS3.3 C.7.6.2.1.1):** For column index $i$ and row index $j$:
  $$\mathbf{P}_{\text{LPS}}(i, j) = \mathbf{S} + i\,\Delta_c\,\mathbf{X} + j\,\Delta_r\,\mathbf{Y} \quad (\text{mm}).$$
- **Exact DICOM LPS (mm) → glTF 2.0 (m) Conversion:** Matching glTF 2.0's right-handed `+X` left, `+Y` up (superior), `+Z` front (anterior) convention in metres is a proper rotation ($\det R = +1$, preserving triangle winding order) scaled by $10^{-3}$:
  $$\begin{pmatrix} x_{\text{glTF}} \\ y_{\text{glTF}} \\ z_{\text{glTF}} \end{pmatrix} = 10^{-3} \begin{pmatrix} 1 & 0 & 0 \\ 0 & 0 & 1 \\ 0 & -1 & 0 \end{pmatrix} \begin{pmatrix} x_{\text{LPS}} \\ y_{\text{LPS}} \\ z_{\text{LPS}} \end{pmatrix} = 10^{-3} \begin{pmatrix} +x_{\text{LPS}} \\ +z_{\text{LPS}} \\ -y_{\text{LPS}} \end{pmatrix}.$$

---

## 3. Actionable Engineering Takeaways for Human Atlas

### 3.1 Physically Grounded Quantization & Validation Tolerance Formulas

Define each mesh's **minimum anatomical feature size** $D_{\min}$ (e.g., smallest physiological lumen diameter or wall/leaflet thickness from §2.3) and **5th-percentile source mesh edge length** $\ell_{\text{p05}}$. To ensure quantization introduces negligible morphometric distortion and never collapses triangles or induces visible normal staircasing:

$$\begin{aligned}
\text{Encoding displacement budget:} \quad \varepsilon_{\text{enc}} &= \frac{\sqrt{3}}{2}\,\Delta \;\le\; \min\!\big(0.01 \cdot D_{\min},\; 0.05 \cdot \ell_{\text{p05}}\big), \\
\text{Required uniform step:} \quad \Delta &\le \frac{2}{\sqrt{3}}\,\varepsilon_{\text{enc}} \approx 1.155\,\varepsilon_{\text{enc}}, \\
\text{Minimum quantization bits for span } S: \quad b_{\min} &= \left\lceil \log_2\!\left(1 + \frac{S}{\Delta}\right) \right\rceil.
\end{aligned}$$

| Anatomical Scale Class | Representative Structures | Primary Morphometric $D_{\min}$ | Target Max Encoding Error $\varepsilon_{\text{enc}}$ | Required Grid Step $\Delta$ | Cross-Atlas Reference NSD Tolerance $\tau$ |
|---|---|---|---|---|---|
| **Retinal / microvascular** | Central retinal artery, lymph node microvessels | `144–163 µm` (Wong 2006; Dorner 2002) | `≤ 1.0 µm` | `≤ 1.15 µm` | `±15–20 µm` (1 SD CRAE) |
| **Thin sheets & ossicles** | Aortic/mitral cusps, stapes, malleus | `250–670 µm` (Sahasakul 1988) | `≤ 2.5 µm` | `≤ 2.88 µm` | `±0.15–0.25 mm` |
| **Coronary & small ducts** | Distal LAD, diagonals, ureteral orifice | `1.5–1.9 mm` (Dodge 1992) | `≤ 10 µm` | `≤ 11.5 µm` | `±0.4–0.6 mm` (Dodge SD) |
| **Medium tubular ducts** | Ureter (non-obstructed / contrast) | `1.8–4.4 mm` (Zelenko 2004; Itanyi 2020) | `≤ 15 µm` | `≤ 17.3 µm` | `±0.9–1.5 mm` (perpendicular to centerline) |
| **Macro organs & bones** | Kidneys, chambers, femurs, spine | `10–450 mm` | `≤ 50 µm` | `≤ 57.7 µm` | `±1.0–2.0 mm` |

### 3.2 Recommended Packing Format & Pipeline Changes

1. **Immediate Spec-Compliance Fix (`MAX_VERTICES`):**
   - Change `MAX_VERTICES = 65536` → **`65535`** in [`tools/import_hra.py`](../../tools/import_hra.py) (and any legacy packers) so no `uint16` index buffer ever emits `65535` (`0xFFFF`, WebGL 2 primitive restart). Alternatively, emit `uint32` indices for chunks exceeding 65,535 vertices.

2. **Short-Term Zero-Dependency Upgrade (Custom Format v2 — Per-Mesh Local Isotropic `uint16` + Optional `float32` / Normals):**
   - Replace layer-global `(mn, sc)` with **per-mesh local isotropic** `(ox, oy, oz, scale)` stored per entry in `m.meta` (+16 bytes/mesh; **0 bytes added to the vertex buffer**). This immediately improves precision by **17×–420×** on small structures (`Left_coronary_artery.l`: `7.85 → 0.203 µm`; `Central_retinal_artery`: `6.76 → 0.386 µm`; `Ureteral_orifice`: `7.10 → 0.153 µm`; `Stapes`: `25.88 → 0.062 µm`), meeting $\varepsilon_{\text{enc}} \le 1\,\mu\text{m}$ for every thin structure without increasing download size.
   - **Seam-safe grouping:** For meshes sharing welded anatomical boundary rings (e.g., ureter–renal pelvis junction, multi-chunk splits of one mesh), assign the **same** cluster `(ox, oy, oz, scale)` to all chunks/parts in that connected anatomical component, following `KHR_mesh_quantization` crack-prevention guidance.
   - **Fallback to `float32`:** If any single connected cluster still violates $b_{\min} > 16$ (i.e., $S_{\text{cluster}} / \Delta > 65535$), store that cluster's positions as `float32` (flag per mesh in `meta`).
   - **Offline normals (eliminating `computeVertexNormals()` artifacts):** Compute smooth area-weighted (or angle-weighted) vertex normals offline on the **unquantized `float32` source mesh** before quantizing positions, and pack normals as 3×`int8` (`snorm8`, 3 B/vertex) or 2×`int8` octahedral encoding (2 B/vertex). This decouples shading quality from position quantization and prevents zero-area collapse from zeroing vertex normals in Three.js r128.

3. **Medium-Term Standards Migration (Native `.glb` + `KHR_mesh_quantization` / `EXT_meshopt_compression`):**
   - Eliminating JSON + Base64 removes a guaranteed **33.3% payload expansion** before HTTP compression.
   - Three.js r128 natively supports `GLTFLoader` with `KHR_mesh_quantization` (since r111) and `EXT_meshopt_compression` (since r122). Packing directly via `gltfpack -kn -ke -vp 16 -vn 10 -cc` preserves named anatomical nodes, `extras` provenance metadata, precomputed normals, `metres` units, and right-handed glTF orientation while shrinking transfer sizes below the current Base64 JSON bundles.

### 3.3 Automated Geometry & Anatomical Validation Suite

Implement a three-tier gate in CI / offline import validation (extending [`tools/test_atlas_data.py`](../../tools/test_atlas_data.py)):

- **Tier 1 — Deterministic Encoding & Mesh Integrity Gate (Source `float32` vs. Decoded Mesh):**
  1. **Vertex fidelity:** $\max_i \|\hat{\mathbf{v}}_i - \mathbf{v}_i\|_2 \le \frac{\sqrt{3}}{2}\Delta$ and $\le \varepsilon_{\text{enc}}$ for the structure's scale class; report 3D RMS displacement ($\approx \Delta / 2$).
  2. **Degeneracy & normal fidelity:** `new_zero_area_faces == 0` (no faces collapsed relative to source); `new_zero_normal_vertices == 0`; 99th-percentile vertex normal angular deviation $\arccos(\hat{\mathbf{n}}_{\text{dec}} \cdot \hat{\mathbf{n}}_{\text{src}}) \le 2^\circ$ (max $\le 5^\circ$ on non-singular vertices).
  3. **Topology & open-surface preservation:** $\Delta V = \Delta F = \Delta\beta_0 = \Delta\chi = \Delta b_{\text{loops}} = 0$; index bounds `max(idx) <= 65534` for `uint16`; no duplicate/identical surfaces across distinct sidebar items.
  4. **Closed-shell gating:** Compute signed volume error $|\Delta V|/V$ ($\le 0.1\%$) **only** when `boundary_edge_count == 0`; flag intentionally open surfaces (`is_open_surface: true`) and verify boundary-loop perimeter drift $\le 0.1\%$.

- **Tier 2 — Surface & Tubular Morphometry Gate (Per *Metrics Reloaded*):**
  1. **Surface distances:** Area-weighted sampled symmetric $\text{HD}$, $\text{HD}_{95}$, $\text{ASSD}$, and $\text{NSD}(\tau)$ against pinned HRA/clinical references using one frozen sampling protocol.
  2. **Tubular centerline QA:** Extract 3D centerlines (maximal inscribed spheres / VMTK protocol) and assert `clDice` connectivity plus **perpendicular-to-centerline** diameter profiles $D_{\text{eq}}(s)$ at named anatomical landmarks (e.g., ureters `15–20 mm` below UPJ vs. Zelenko `1.8 ± 0.9 mm` / Itanyi `4.3–4.4 mm`; coronaries at LMCA / prox-LAD / dist-LAD vs. Dodge 1992 & Medrano-Gracia 2016; CRA vs. `144–163 µm`).

- **Tier 3 — Calibration & Provenance Schema (Per-Model Metadata):**
  - Store per-layer/per-mesh `extras`: `source_doi` / `hubmap_id`, `release_version`, `units: "m"`, `coordinate_frame: "glTF-2.0-RH-Yup-Zfront"`, `dicom_lps_to_gltf` (when image-derived), `ontology_id` (`UBERON`/`FMA`), `is_open_surface`, and `quantization_step_um`.

---

## 4. Primary References

1. **Khronos Group.** *glTF 2.0 Specification (ISO/IEC 12113:2022)*. [https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) (Sections: `#coordinate-system-and-units`, `#accessor-data-types`, `#data-alignment`, `#meshes-topology`, `#binary-gltf-layout`, `#chunks-v2`).
2. **Khronos Group.** *WebGL 2.0 Specification*, §5.14 (`PRIMITIVE_RESTART_FIXED_INDEX is always enabled`). [https://registry.khronos.org/webgl/specs/latest/2.0/](https://registry.khronos.org/webgl/specs/latest/2.0/).
3. **Kapoulkine A, Knyazev A (Khronos Group).** *`KHR_mesh_quantization` glTF 2.0 Extension Specification*. [https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_mesh_quantization](https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_mesh_quantization).
4. **Google Draco Authors.** *Draco 3D Geometry Compression Library*: `attribute_quantization_transform.cc` & `quantization_utils.h`. [https://github.com/google/draco](https://github.com/google/draco).
5. **Kapoulkine A.** *meshoptimizer & gltfpack Documentation*. [https://github.com/zeux/meshoptimizer](https://github.com/zeux/meshoptimizer) and [`gltf/README.md`](https://github.com/zeux/meshoptimizer/blob/master/gltf/README.md).
6. **Three.js Authors (r128).** `src/core/BufferGeometry.js` (`computeVertexNormals`, `normalizeNormals`) and `src/math/Vector3.js` (`normalize`). [https://github.com/mrdoob/three.js/tree/r128](https://github.com/mrdoob/three.js/tree/r128).
7. **Maier-Hein L, Reinke A, Godau P, et al.** Metrics reloaded: recommendations for image analysis validation. *Nature Methods*. 2024;21(2):195–212. DOI: [10.1038/s41592-023-02151-z](https://doi.org/10.1038/s41592-023-02151-z) · PMID: `38347141` · PMCID: [PMC11182665](https://pmc.ncbi.nlm.nih.gov/articles/PMC11182665/).
8. **Reinke A, Tizabi MD, Baumgartner M, et al.** Understanding metric-related pitfalls in image analysis validation. *Nature Methods*. 2024;21(2):182–194. DOI: [10.1038/s41592-023-02150-0](https://doi.org/10.1038/s41592-023-02150-0) · PMID: `38347140` · PMCID: [PMC11181963](https://pmc.ncbi.nlm.nih.gov/articles/PMC11181963/).
9. **Cignoni P, Rocchini C, Scopigno R.** *Metro*: Measuring Error on Simplified Surfaces. *Computer Graphics Forum*. 1998;17(2):167–174. DOI: [10.1111/1467-8659.00236](https://doi.org/10.1111/1467-8659.00236).
10. **Shit S, Paetzold JC, Sekuboyina A, et al.** clDice — a Novel Topology-Preserving Loss Function for Tubular Structure Segmentation. *IEEE/CVF CVPR*. 2021:16560–16569. DOI: [10.1109/cvpr46437.2021.01629](https://doi.org/10.1109/cvpr46437.2021.01629).
11. **Börner K, Teichmann SA, Quardokus EM, et al.** Anatomical structures, cell types and biomarkers of the Human Reference Atlas. *Nature Cell Biology*. 2021;23(11):1117–1128. DOI: [10.1038/s41556-021-00788-6](https://doi.org/10.1038/s41556-021-00788-6) · PMID: `34750582` · PMCID: [PMC10079270](https://pmc.ncbi.nlm.nih.gov/articles/PMC10079270/).
12. **Herr BW II, Hardi J, Quardokus EM, ..., Börner K.** Specimen, biological structure, and spatial ontologies in support of a Human Reference Atlas. *Scientific Data*. 2023;10:171. DOI: [10.1038/s41597-023-01993-8](https://doi.org/10.1038/s41597-023-01993-8) · PMID: `36973309` · PMCID: [PMC10043028](https://pmc.ncbi.nlm.nih.gov/articles/PMC10043028/).
13. **Boppana A, Lee S, Malhotra R, ..., Börner K, Weber GM.** Anatomical structures, cell types, and biomarkers of the healthy human blood vasculature. *Scientific Data*. 2023;10:452. DOI: [10.1038/s41597-023-02018-0](https://doi.org/10.1038/s41597-023-02018-0) · PMID: `37468503` · PMCID: [PMC10356915](https://pmc.ncbi.nlm.nih.gov/articles/PMC10356915/).
14. **Quardokus EM, Schlehlein H, Bueckle A.** *SOP: Adding 3D Reference Objects to the Human Reference Atlas* (v1.2.0). Zenodo, 2023. DOI: [10.5281/zenodo.10358858](https://doi.org/10.5281/zenodo.10358858). **Quardokus EM, Bueckle A, Börner K, Record E, Browne K.** *SOP: 3D Reference Object Approval* (v2.2.0). Zenodo, 2022. DOI: [10.5281/zenodo.5944197](https://doi.org/10.5281/zenodo.5944197).
15. **HuBMAP Consortium.** *CCF Releases v1.1 & v1.2 Reference Organ Metadata & Mapping Repository*. [https://github.com/hubmapconsortium/ccf-releases](https://github.com/hubmapconsortium/ccf-releases).
16. **Dodge JT Jr, Brown BG, Bolson EL, Dodge HT.** Lumen diameter of normal human coronary arteries. Influence of age, sex, anatomic variation, and left ventricular hypertrophy or dilation. *Circulation*. 1992;86(1):232–246. DOI: [10.1161/01.cir.86.1.232](https://doi.org/10.1161/01.cir.86.1.232) · PMID: `1535570`.
17. **Medrano-Gracia P, Ormiston J, Webster M, et al.** A computational atlas of normal coronary artery anatomy. *EuroIntervention*. 2016;12(7):845–854. DOI: [10.4244/EIJV12I7A139](https://doi.org/10.4244/EIJV12I7A139) · PMID: `27639736`.
18. **Sahasakul Y, Edwards WD, Naessens JM, Tajik AJ.** Age-related changes in aortic and mitral valve thickness: implications for two-dimensional echocardiography based on an autopsy study of 200 normal human hearts. *Am J Cardiol*. 1988;62(7):424–430. DOI: [10.1016/0002-9149(88)90971-x](https://doi.org/10.1016/0002-9149(88)90971-x) · PMID: `3414519`.
19. **Dorner GT, Polska E, Garhöfer G, Zawinka C, Frank B, Schmetterer L.** Calculation of the diameter of the central retinal artery from noninvasive measurements in humans. *Curr Eye Res*. 2002;25(6):341–345. DOI: [10.1076/ceyr.25.6.341.14231](https://doi.org/10.1076/ceyr.25.6.341.14231) · PMID: `12789540`.
20. **Knudtson MD, Lee KE, Hubbard LD, Wong TY, Klein R, Klein BEK.** Revised formulas for summarizing retinal vessel diameters. *Curr Eye Res*. 2003;27(3):143–149. DOI: [10.1076/ceyr.27.3.143.16049](https://doi.org/10.1076/ceyr.27.3.143.16049) · PMID: `14562179`.
21. **Wong TY, Islam FMA, Klein R, et al.** Retinal vascular caliber, cardiovascular risk factors, and inflammation: the Multi-Ethnic Study of Atherosclerosis (MESA). *Invest Ophthalmol Vis Sci*. 2006;47(6):2341–2350. PMID: `16723443`.
22. **Yip W, Tham YC, Hsu W, et al.** Comparison of Common Retinal Vessel Caliber Measurement Software and a Conversion Algorithm. *Transl Vis Sci Technol*. 2016;5(5):11. PMID: `27752402`.
23. **Kocabiyik N, Yalcin B, Ozan H.** The morphometric analysis of the central retinal artery. *Ophthalmic Physiol Opt*. 2005;25(4):375–378. DOI: [10.1111/j.1475-1313.2005.00286.x](https://doi.org/10.1111/j.1475-1313.2005.00286.x) · PMID: `15953124`.
24. **Zelenko N, Coll D, Rosenfeld AT, Smith RC.** Normal ureter size on unenhanced helical CT. *AJR Am J Roentgenol*. 2004;182(4):1039–1041. DOI: [10.2214/ajr.182.4.1821039](https://doi.org/10.2214/ajr.182.4.1821039) · PMID: `15039184`.
25. **Itanyi UD, Aiyekomogbon JO, Uduma FU, Evinemi MA.** Assessment of ureteric diameter using contrast-enhanced helical abdominal computed tomography. *African Journal of Urology*. 2020;26(1). DOI: [10.1186/s12301-020-00021-0](https://doi.org/10.1186/s12301-020-00021-0).
26. **Antiga L, Piccinelli M, Botti L, Ene-Iordache B, Remuzzi A, Steinman DA.** An image-based modeling framework for patient-specific computational hemodynamics (VMTK). *Med Biol Eng Comput*. 2008;46(11):1097–1112. DOI: [10.1007/s11517-008-0420-1](https://doi.org/10.1007/s11517-008-0420-1) · PMID: `19002516`.
27. **NEMA / DICOM Standards Committee.** *DICOM PS3.3: Information Object Definitions*, Section C.7.6.2 Image Plane Module & C.7.6.2.1.1 Image Position and Image Orientation. [https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.7.6.2.html](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_c.7.6.2.html).
