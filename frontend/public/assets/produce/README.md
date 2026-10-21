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

`onion.glb` uses **Yellow Onion** by **Kuutti Siitonen**, published by
[Poly Haven](https://polyhaven.com/a/yellow_onion) under CC0. `onion-sources.json`
records the five verified sources and output checksum. The source becomes
249/1,399-triangle LODs; all three original 1K JPEG maps are retained byte for
byte. Instances restore the upright 7.25 × 8.64 × 6.86 cm proportions before the
common 10% product readability scale.

Whole yellow/brown onion names use the scan. Red, white, sweet, green, spring and
pearl varieties, peeled or processed onions, planting sets and multipacks retain
their existing packaging. Shelf and table displays use one layer. Stable
half-turn, size and brightness variation stays inside each display footprint.
High uses the photographic normal and roughness maps; Medium uses color with
flat roughness. A warm brown bulb with a tapered neck remains visible while
loading or after failure. Layouts without whole onions do not request the asset.

Download and verify the manifest sources, preserving their paths, then run:

```sh
blender --background --python scripts/convert_onion.py -- \
  --source-dir /path/to/onions --output frontend/public/assets/produce/onion.glb
```

`kiwi.glb` uses **Food Kiwi 01** by **Oliver Harries**, published by
[Poly Haven](https://polyhaven.com/a/food_kiwi_01) under CC0. `kiwi-sources.json`
records the original files, hashes, authored dimensions and converted output.
The fruit lies on its side at approximately 90.1 × 69.5 × 68.6 mm. Its two
detail levels contain 240 and 1,200 triangles, with bottom-centred unit bounds
and inverse-transpose normal correction. Original 1K JPEG color, OpenGL normal
and roughness maps are retained; the fuzzy skin detail is in these maps.

Whole green/Hayward kiwi names use the scan. Gold or baby varieties, processed
fruit, juices and multipacks retain their package representation. Shelf and
table stock stays in one layer with small, stable scale/brightness changes and
half-turn variation. Medium uses the photo color with a matte nonmetallic
surface; High adds the normal and roughness maps. A brown oval fallback remains
visible during loading or after failure, and absent kiwis cause no request.

Rebuild with Blender 4.3.2 after downloading and verifying the manifest files:

```sh
blender --background --python scripts/convert_kiwi.py -- \
  --source-dir /path/to/kiwis --output frontend/public/assets/produce/kiwi.glb
```

`sweet-potato.glb` uses **Sweet Potato** by **Jan Martens**, published by
[Poly Haven](https://polyhaven.com/a/sweet_potato) under CC0. The adjacent
`sweet-potato-sources.json` records all five verified sources and output hashes.
The scan lies on its side at approximately 100.5 × 58.1 × 61.0 mm before the
common product readability scale. Its 240/1,199-triangle LODs share original
1K JPEG color, OpenGL normal and packed roughness/metalness maps, retained byte
for byte. The authored metallic factor remains zero.

Whole raw sweet potato names use this reddish-skinned scan. Other named
varieties, yams, ordinary potatoes, cooked or cut food, plants and multipacks
retain their existing package rules. Shelf and table displays use one layer,
with stable half-turn, size and brightness variation. Medium uses photographic
color and matte shading; High adds normal and roughness maps. A tapered brown
fallback stays visible during loading or failure. Absent sweet potatoes cause
no request for the asset.

Rebuild with Blender 4.3.2 after downloading and verifying the manifest files:

```sh
blender --background --python scripts/convert_sweet_potato.py -- \
  --source-dir /path/to/sweet-potatoes --output frontend/public/assets/produce/sweet-potato.glb
```

`asian-pear.glb` uses the upright **E** fruit from **Pears Asian 01** by
**Amal Kumar**, published by [Poly Haven](https://polyhaven.com/a/food_pears_asian_01)
under [CC0](https://polyhaven.com/license). The adjacent `asian-pear-sources.json`
records all five verified sources and output hashes. The source arrangement
contains five fruits; only one intact fruit is instanced in the store. Its
source dimensions, including the stem, are approximately 43.4 × 67.0 × 43.4 mm
before the common product readability scale.

The 299/1,400-triangle LODs retain the original 1K JPEG color, OpenGL normal and
packed roughness/metalness maps byte for byte. The authored metallic factor
remains zero. Whole Asian/Nashi pear names use the yellow-green scan; generic
pears, other named cultivars, processed foods, plants and multipacks retain
existing package rules. Shelf and table displays use one layer with stable
half-turn, size and brightness variation. Medium uses photographic color and
matte shading; High adds normal and roughness maps. A round, stemmed fallback
stays visible during loading or failure. Absent Asian pears cause no request
for the asset.

Rebuild with Blender 4.3.2 after downloading and verifying the manifest files:

```sh
blender --background --python scripts/convert_asian_pear.py -- \
  --source-dir /path/to/asian-pears --output frontend/public/assets/produce/asian-pear.glb
```


`ginger.glb` uses **Food Ginger 01** by **Oliver Harries**, published by
[Poly Haven](https://polyhaven.com/a/food_ginger_01) under CC0.
`ginger-sources.json` records five verified sources and the output checksum.
The 7,205-triangle source becomes 300/1,400-triangle LODs, sharing its original
1K JPEG color, OpenGL normal and roughness maps in a 467,632-byte model.

The long axis is laid across the display and uniformly scaled by 0.35, giving
approximately 20.1 × 5.2 × 8.4 cm before the usual product readability scale.
This is an artistic retail display size, not a measured root size. Both LODs
have bottom-centred unit bounds; inverse-transpose normals preserve the lighting
when the instances restore these proportions.

Whole fresh/raw ginger and ginger-root names use the scan. Drinks, powders,
pastes, pickled or cut ginger, supplements, plants and multipacks retain their
package rules. Shelf and table displays use one layer with stable half-turn,
size and brightness variation. Medium uses color and flat roughness; High also
uses normal and roughness maps. A knobbly procedural root stays visible during
loading or failure; a store without whole ginger makes no model request.

Download and verify the manifest sources, preserving paths, then run:

```sh
blender --background --python scripts/convert_ginger.py -- \
  --source-dir /path/to/ginger --output frontend/public/assets/produce/ginger.glb
```
