# Data notice (folder `data/`)

The main body layers contain 3D model data derived from:

- **Z-Anatomy**, licensed under CC BY-SA 4.0 (https://github.com/Z-Anatomy)
- **BodyParts3D**, © The Database Center for Life Science (DBCLS), Japan

The data has been **modified**: objects were selected, exact duplicate meshes
removed, some meshes simplified, vertex positions quantized, and everything
packed into a compact binary format encoded as base64 JSON.

## HuBMAP reference models

The six layers below use the [HuBMAP Human Reference Atlas 3D Reference Object Library](https://humanatlas.io/3d-reference-library), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit HuBMAP, Kristen Browne and Heidi Schlehlein, with the source records below. The reference views preserve the GLB transforms and metre units. The importer selects and groups meshes, quantizes the vertices, and splits oversized meshes at triangle boundaries for 16-bit indices.

| Atlas data | Source GLB files | Source record |
|---|---|---|
| `atlas_jantung.json` | `v1.1/VH_M_Heart.glb` | [Heart, male, Kristen Browne](https://doi.org/10.48539/HBM548.CTHS.699) |
| `atlas_urin.json` | `v1.2/VH_M_Kidney_L.glb`, `VH_M_Kidney_R.glb`, `VH_M_Ureter_L.glb`, `VH_M_Ureter_R.glb`, `VH_M_Urinary_Bladder.glb`, `VH_M_Urethra.glb` | [Urinary reference objects and credits](https://github.com/hubmapconsortium/ccf-releases/tree/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.2/markdown/ref-organs) · [Right ureter](https://doi.org/10.48539/HBM878.DBSR.759) |
| `atlas_limfa.json` | `v1.2/VH_M_Spleen.glb`, `VH_M_Thymus.glb` | [Spleen](https://doi.org/10.48539/HBM662.GMWC.569) · [Thymus](https://doi.org/10.48539/HBM823.SNLN.667) |
| `atlas_limfonodus.json` | `v1.2/NIH_M_Lymph_Node.glb` | [Lymph node, male](https://doi.org/10.48539/HBM299.VVXH.634) |
| `atlas_ususHalus.json` | `v1.2/VH_M_Small_Intestine.glb` | [Small intestine, male](https://github.com/hubmapconsortium/ccf-releases/blob/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.2/markdown/ref-organs/small-intestine-male.md) |
| `atlas_ususBesar.json` | `v1.2/SBU_M_Intestine_Large.glb` | [Large intestine, male, based on data from Arie Kaufman, Stony Brook University](https://doi.org/10.48539/HBM334.LVTH.937) |

To rebuild these layers, get the listed GLBs from the `models/` folder in the pinned [v1.1](https://github.com/hubmapconsortium/ccf-releases/tree/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.1/models) or [v1.2](https://github.com/hubmapconsortium/ccf-releases/tree/b036a91aaf7234f462b1249d4a5f4fb0e982f412/v1.2/models) release. Place them in `v11/` and `v12/` subdirectories of a source directory and run `python3 tools/import_hra.py <source-directory>` from the repository. The script uses NumPy and updates the six packed data files and their sidebar mappings. Normal website use requires only the shipped JSON files.

The original body geometry and the HuBMAP references use different coordinate frames and specimens. The viewer disables the original skeleton overlay for the reference layers. The heart shows complete valve objects and a septum. The lymphatic views show the spleen, thymus, and parts of one lymph node. The bowel views show the ileum, cecum and rectum. The source collections do not provide separately selectable chordae tendineae, a whole-body lymphatic network, or the anal canal in these views. [Initial anatomy audit](../ANATOMY-REVIEW.md)

In a horizontal section 20 mm below each ureter mesh's highest vertex, the old model spans 10.75 mm on the left and 8.15 mm on the right. The HuBMAP replacements span 4.44 mm and 4.50 mm in the same measurement. These are outer mesh spans. CT studies use an anatomical landmark and an imaging protocol to measure calibre. [CT comparison](https://pubmed.ncbi.nlm.nih.gov/15039184/)

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

> 3D models: BodyParts3D © The Database Center for Life Science, via Z-Anatomy
> (CC BY-SA 4.0), processed and simplified for the web.

Please also check the Z-Anatomy repository for the attribution wording it
requests, and for the licenses of individual models.

## Full license text

Place the full legal code of CC BY-SA 4.0 in a file named `LICENSE` in this
folder (copy it from the "Read the Legal Code" link on the Creative Commons
page above).
