# Photographic shopper avatars

Microsoft Rocketbox Avatar Library, MIT License, Copyright (c) 2020 Microsoft.
See `LICENSE.txt` for the full license. Models and motion clips are adapted from
the pinned source revision and SHA-256 records in `sources.json`.

- `female-01.glb`: Female_Adult_01, 8,732 triangles.
- `male-01.glb`: Male_Adult_01.
- Each includes `idle` and `walk` clips. Independent skeletons animate each shopper.
- Textures are resized to 1024 px: JPEG for opaque color, PNG for normal maps
  and hair alpha. Skin and cloth retain different roughness values.
- The original FBX skeletons use different rest poses for each motion. Bone
  orientations are baked into the avatar's own rest skeleton. Forward root
  travel is removed; the simulation owns shopper position.
- Hair uses alpha testing to avoid transparency sorting problems in crowds.
- This first set contains two visual variants. Avatars are representative
  figures, not reconstructions of individual simulated consumers.

The application loads these GLBs locally and makes no requests to Microsoft.
Classic mode retains the existing lightweight characters.

To rebuild, download the `files` listed in `sources.json` into a source directory,
preserving their `file` paths. Verify each SHA-256, then run from the repo root:

```sh
blender --background --python scripts/convert_rocketbox.py -- \
  --source-dir /path/to/rocketbox --output-dir frontend/public/assets/people \
  --model Female_Adult_01
blender --background --python scripts/convert_rocketbox.py -- \
  --source-dir /path/to/rocketbox --output-dir frontend/public/assets/people \
  --model Male_Adult_01
```

The conversion was built with Blender 4.3.2. Refresh the output file sizes and
checksums in `sources.json` after conversion.
