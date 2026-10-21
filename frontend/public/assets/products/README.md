# Scanned retail products

`terracotta-pot.glb` isolates the hollow pot from **Potted Plant 01** by
**Rico Cilliers**, published by [Poly Haven](https://polyhaven.com/a/potted_plant_01)
under [CC0](https://polyhaven.com/license). `sources.json` records source URLs,
SHA-256 checksums, authored dimensions and the bundled output checksum.

The 5,440-triangle pot becomes 299 triangles for overview and 1,500 for close
views, sharing the original 1K JPEG color, OpenGL normal and roughness maps.
The plant, stem and pebbles are excluded. The open interior and rim remain.

Terracotta or clay plant-pot names use this scan. An explicit diameter in cm
sets the width (20 cm when unspecified); the source height-to-width ratio is
preserved, including when fitting a small shelf slot. The usual 10% product
readability scale still applies. Pots use one layer on shelves and tables.
Unsupported multipacks and unrelated products retain their usual packages.

One instanced draw covers the pots. High uses all PBR maps; Medium uses color
and constant roughness. A hollow procedural pot stays visible while loading or
if the scan fails. Layouts without pots make no request for this model.

To reproduce, download and verify all manifest files, preserving their listed
paths. Rename the source `potted_plant_01_1k.gltf` to `potted_plant_01.gltf`.
The full source model dependencies are needed for import, although only the
pot and its textures are exported. Run with Blender 4.3.2:

```sh
blender --background --python scripts/convert_terracotta_pot.py -- \
  --source-dir /path/to/potted-plant-01 \
  --output frontend/public/assets/products/terracotta-pot.glb
```

`croissant.glb` uses **Croissant**, scanned by **Dario Barresi** and processed by
**Greg Zaal**, published by [Poly Haven](https://polyhaven.com/a/croissant) under
the same CC0 license. `croissant-sources.json` records all source and output hashes.
The 1,990-triangle source becomes 300/1,500-triangle LODs with the original 1K JPEG
color, OpenGL normal and packed roughness maps. The bundled file is 2,095,144 bytes.

Plain or butter croissants use the scan, retaining its approximately
20.0 × 6.2 × 7.6 cm dimensions before the usual product readability scale.
Both shelves and display tables keep pastries in one layer and preserve their
proportions when fitting a small slot. Filled croissants, sandwiches and explicit
multipacks retain their package geometry. Medium uses color and constant roughness;
High adds the normal and roughness maps. A tapered pastry fallback stays visible
while loading or if the scan fails. Only layouts with croissants request the model.

Download and verify the croissant manifest, preserving paths and renaming
`croissant_1k.gltf` to `croissant.gltf`, then run:

```sh
blender --background --python scripts/convert_croissant.py -- \
  --source-dir /path/to/croissant \
  --output frontend/public/assets/products/croissant.glb
```
