# Photographic shopper avatars

Microsoft Rocketbox Avatar Library, MIT License, Copyright (c) 2020 Microsoft.
See `LICENSE.txt` for the full license. Models and motion clips are adapted from
the pinned source revision and SHA-256 records in `sources.json`.

- `female-01.glb`: Female_Adult_01, 8,732 triangles.
- `male-01.glb`: Male_Adult_01, 7,440 triangles.
- `female-14.glb`: Female_Adult_14, cardigan and boots.
- `male-14.glb`: Male_Adult_14, shirt and trousers.
- `female-11.glb`: Female_Adult_11, dress and boots, 8,896 triangles.
- `male-12.glb`: Male_Adult_12, denim jacket and jeans.
- Each includes captured `idle`, `walk`, and `browse` clips. Browsing shoppers
  turn their head and shoulders to look around the shelf. Independent skeletons
  and motion phases animate each shopper. Authored metric heights are preserved.
- Color, normal and hair-alpha textures are resized to 1024 px: JPEG for opaque
  color, PNG for normal maps and hair alpha. Face and body materials also carry
  512 px roughness maps derived from the original specular textures, so eyes,
  skin, hair, fabric and shoes do not all reflect light with a uniform gloss.
- This is an artistic conversion of legacy specular data, not measured PBR
  roughness. With source luminance `s` in [0, 1], the face uses
  `0.64 - 0.44 * sqrt(s)` and the body uses `0.90 - 0.65 * sqrt(s)`.
  These bounded curves retain matte skin and clothing while preserving the
  original map's locations of stronger highlights. Materials remain nonmetallic.
- The original FBX skeletons use different rest poses for each motion. Bone
  orientations are baked into the avatar's own rest skeleton. Forward root
  travel is removed; the simulation owns shopper position.
- Hair uses alpha testing to avoid transparency sorting problems in crowds.
- This set contains six visual variants, selected deterministically by shopper ID. Avatars are representative
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

Repeat the same command with `Female_Adult_14`, `Male_Adult_14`, `Female_Adult_11`,
and `Male_Adult_12` for the other variants.

The conversion was built with Blender 4.3.2. Refresh the output file sizes and
checksums in `sources.json` after conversion.
