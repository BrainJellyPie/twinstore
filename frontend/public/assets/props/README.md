# Photographic storefront plants

`potted-plant-01.glb` is adapted from [Poly Haven Potted Plant 01](https://polyhaven.com/a/potted_plant_01)
by Rico Cilliers, under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
All source URLs, byte counts and SHA-256 hashes are in `sources.json`.

The source's 176,226 triangles are reduced to 14,499, with most of the budget
retained on leaves. The separate source alpha map is restored into the leaf
color texture; leaves use alpha testing instead of transparent sorting. The
1K color, normal and roughness maps are embedded in the GLB. Its approximately
1.35 m authored height is preserved using the viewer's metre-to-world scale.

High quality loads one local model shared by the planters outside each doorway.
Medium and failed or pending downloads use the original procedural planters.
No request is made when the store has no exterior doorway. Leaving High releases the
loaded model's GPU resources and image bitmaps.

To rebuild, download and verify the `files` in `sources.json`, preserving their
relative paths, then run with Blender 4.3.2:

```sh
blender --background --python scripts/convert_potted_plant.py -- \
  --source-dir /path/to/potted-plant-01 \
  --output frontend/public/assets/props/potted-plant-01.glb
```
