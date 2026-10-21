# Scanned produce

`bananas.glb` uses **Bananas** by **Alexander Shulha**, published by
[Poly Haven](https://polyhaven.com/a/bananas) under
[CC0](https://polyhaven.com/license). Source URLs, SHA-256 hashes and the converted
file checksum are recorded in `sources.json`.

The original bunch is reduced from 25,876 triangles to 300 for the overview and
1,600 for close views. Both meshes share the original 1K JPEG color, normal and
packed roughness maps. Their geometry is normalized to a bottom-centred unit box;
product instances restore the authored proportions of approximately
13.4 × 17.9 × 22.3 cm. The store's usual 10% product readability scale still applies.

Fresh banana names use the scan. Banana bread, chips, milk and ice cream keep
their package geometry. One instanced draw covers the store's bunches. Medium
quality uses the color map with flat roughness; High also uses the normal and
roughness maps. A curved procedural bunch stays visible during loading or if the
asset cannot be loaded. No model request is made when the layout has no bananas.

To reproduce, download the manifest's source files into one directory, preserving
the listed paths (`bananas.gltf` is the source's `bananas_1k.gltf` renamed locally),
verify their hashes, and run:

```sh
blender --background --python scripts/convert_bananas.py -- \
  --source-dir /path/to/bananas --output frontend/public/assets/produce/bananas.glb
```

Built with Blender 4.3.2. The application loads the model locally.

`apples.glb` uses **Food Apple 01** by **Oliver Harries**, published by
[Poly Haven](https://polyhaven.com/a/food_apple_01) under the same CC0 license.
`apple-sources.json` records the source files, hashes and converted output.
The 7,012-triangle source becomes 200/999-triangle single apples and
400/1,998-triangle pairs. All four meshes share the original 1K JPEG color,
OpenGL normal and roughness maps; the bundled model is 428,616 bytes.

The authored single-apple dimensions are approximately 9.76 × 8.54 × 9.59 cm.
A two-pack contains two apples with a 6 mm gap, maintaining each fruit's shape.
Fresh red-apple names and explicit two-packs use these formats; apple juice,
chips, pie and unsupported pack sizes keep their usual package geometry.
Both formats load one shared asset per store. Produce stays in one shelf layer
and retains its proportions when fitted to a small slot. Medium uses color only;
High also uses normal and roughness maps. Rounded red fallbacks remain available.

Download and verify the apple manifest sources, renaming the source
`food_apple_01_1k.gltf` to `food_apple_01.gltf`, then run:

```sh
blender --background --python scripts/convert_apples.py -- \
  --source-dir /path/to/apples --output frontend/public/assets/produce/apples.glb
```

`avocado.glb` uses **Food Avocado 01** by **Oliver Harries**, published by
[Poly Haven](https://polyhaven.com/a/food_avocado_01) under CC0.
`avocado-sources.json` records the five verified source files and output checksum.
The 7,743-triangle source becomes 200/999-triangle LODs sharing the original
1K JPEG color, OpenGL normal and roughness maps; the bundled file is 441,080 bytes.
Instances restore the authored proportions of approximately 9.52 × 14.32 × 9.46 cm.

Whole fresh and Hass avocado names use the scan. Oils, spreads, chips, halves,
explicit green varieties and multiple packs keep their existing package rules.
Shelf and table displays use one layer. Stable size, half-turn and brightness
variation keeps each fruit within its display footprint. Medium uses color with
flat roughness, while High retains the normal and roughness maps. A tapered
procedural fruit remains visible during loading or if the model is unavailable;
layouts without avocados make no request for this asset.

Download and verify the avocado manifest sources, renaming
`food_avocado_01_1k.gltf` to `food_avocado_01.gltf`, then run:

```sh
blender --background --python scripts/convert_avocado.py -- \
  --source-dir /path/to/avocados --output frontend/public/assets/produce/avocado.glb
```

`lemon.glb` uses **Lemon** by **Kuutti Siitonen**, published by
[Poly Haven](https://polyhaven.com/a/lemon) under CC0. `lemon-sources.json`
records the five verified source files and output checksum. The 4,012-triangle
source becomes 200/1,000-triangle LODs with original 1K JPEG color, OpenGL normal
and packed roughness maps. The fruit lies on its side at approximately
9.54 × 6.87 × 6.83 cm before the common 10% product readability scale.

Whole yellow lemon names use the scan; juices, preserved or cut fruit, Meyer
varieties and multipacks retain their existing package rules. Shelf and table
displays use one layer and preserve proportions. Half-turn, size and brightness
variation stays within each display footprint. Medium uses color and flat
roughness; High adds normal and roughness maps. A pointed procedural fallback
remains visible during loading or failure; absent lemons cause no asset request.

Download and verify the manifest files, preserving their paths, then run:

```sh
blender --background --python scripts/convert_lemon.py -- \
  --source-dir /path/to/lemons --output frontend/public/assets/produce/lemon.glb
```
