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

`watering-can.glb` uses **Watering Can Metal 01** by **Charles Nderitu**,
published by [Poly Haven](https://polyhaven.com/a/watering_can_metal_01) under
CC0. `watering-can-sources.json` records source hashes and the converted output.
The 11,837-triangle source becomes 499/2,500-triangle LODs, sharing the original
1K JPEG color, OpenGL normal and packed metallic/roughness maps. The spout is
turned along the shelf width; dimensions remain approximately 45.2 × 19.7 × 19.1 cm
before the product readability scale. Handles, spout and sprinkler head are retained.

Generic or metal watering-can names and the catalog's `Watering Can 5L` use this
representative model. Explicit plastic models, other capacities and multipacks
retain their existing geometry. The source does not specify a measured capacity;
the viewer preserves its authored dimensions without inferring volume from the label.
Cans retain their proportions and stay in one layer on shelves and tables.
High uses the full reflective material. Medium uses diffuse color and constant
roughness, since it has no scene environment for metallic reflections. A
procedural body, handle and spout remain visible during loading or failure.
Layouts without watering cans do not request the scan.

Download and verify the manifest, preserving paths and renaming
`watering_can_metal_01_1k.gltf` to `watering_can_metal_01.gltf`, then run:

```sh
blender --background --python scripts/convert_watering_can.py -- \
  --source-dir /path/to/watering-can \
  --output frontend/public/assets/products/watering-can.glb
```


`burger-bun.glb` uses **Hamburger Buns** by **Alexander Shulha**, published by
[Poly Haven](https://polyhaven.com/a/hamburger_buns) under CC0.
`burger-bun-sources.json` records five verified sources and the output checksum.
The middle roll (`hamburger_buns_02`) retains its original 3,950 triangles for
close views and uses 200 triangles at a distance. Decimating the close-view
surface introduced visible shading boundaries, so the original curvature is
preserved. Both LODs share the original 1K JPEG color, OpenGL
normal and packed roughness maps in a 2,140,696-byte model.

The authored proportions remain approximately 11.1 × 5.8 × 10.6 cm before the
usual product readability scale. Singular plain hamburger/burger-bun names and
explicit individual sales (`Each`, `Loose`, `Single`) use the scan. Unqualified
plural names, multipacks, seeded or specialty rolls, frozen bread and filled
burgers retain their existing package rules.

Shelves and tables keep rolls in one layer, preserving their proportions and
adding stable half-turn, size and brightness variation within each footprint.
Medium uses color and flat roughness; High also uses normal and roughness maps.
A closed dome with a flat base stays visible during loading or failure. Layouts
without individual plain burger buns make no request for the asset.

Download and verify the manifest sources, preserving paths, then run:

```sh
blender --background --python scripts/convert_burger_bun.py -- \
  --source-dir /path/to/hamburger-buns --output frontend/public/assets/products/burger-bun.glb
```
