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
