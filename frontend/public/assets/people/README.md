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
- Each includes captured `idle`, `wait`, `walk`, and `browse` clips. Browsing shoppers
  turn their head and shoulders to look around the shelf. Independent skeletons
  and motion phases animate each shopper. Authored metric heights are preserved.
- Standing shoppers deterministically choose either breathing or a longer neutral
  posture variation from `f_idle_neutral_02` / `m_idle_neutral_02` (11.27 / 15.53 s).
  Small head turns and weight shifts vary the crowd's resting poses. Both clips
  loop continuously, cross-fade into walking or browsing, and freeze with playback.
  This visual variation does not change simulated actions or attention.
- The facial FBX's authored `AU_45_Blink` shape is retained as `blink`.
  Eyelids close and reopen over 0.23 seconds, with
  deterministic per-shopper intervals of 3.2–6 seconds. This cosmetic motion
  pauses with playback and stays at a natural rate during accelerated simulation.
- Authored `AU_61`–`AU_64` shapes supply small left/right/up/down gaze shifts.
  Shoppers hold each fixation for 1.8–3.2 seconds and transition over 90 ms,
  with distinct deterministic schedules. Horizontal weights stay within 0.3;
  vertical weights stay within 0.16. Gaze fades under a blink to preserve closed
  eyelids, and pauses with playback. These cosmetic shifts do not represent
  simulated attention or change shopping decisions. Other facial shapes are omitted.
- Color, normal and hair-alpha textures are resized to 1024 px: JPEG for opaque
  color, lossless WebP for normal maps, and PNG for hair alpha. Face and body materials also carry
  512 px roughness maps derived from the original specular textures, so eyes,
  skin, hair, fabric and shoes do not all reflect light with a uniform gloss.
- This is an artistic conversion of legacy specular data, not measured PBR
  roughness. With source luminance `s` in [0, 1], the face uses
  `0.64 - 0.44 * sqrt(s)` and the body uses `0.90 - 0.65 * sqrt(s)`.
  These bounded curves retain matte skin and clothing while preserving the
  original map's locations of stronger highlights. Materials remain nonmetallic.
- Normal maps use `EXT_texture_webp`, supported natively by Three's glTF loader.
  The converter verifies identical decoded RGBA pixels before replacing the PNG
  buffers; geometry, rig, animations and other image buffers are left intact.
- The original FBX skeletons use different rest poses for each motion. Bone
  orientations are baked into the avatar's own rest skeleton. Forward root
  travel is removed; the simulation owns shopper position.
- Hair uses alpha testing to avoid transparency sorting problems in crowds.
- This set contains six visual variants, selected deterministically by shopper ID. Avatars are representative
  figures, not reconstructions of individual simulated consumers.

The application loads these GLBs locally and makes no requests to Microsoft.
Classic mode retains the existing lightweight characters. Its character and
fixture assets are preloaded only when Classic is selected, keeping the first
Realistic view focused on the photographic assets it actually displays.

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

The conversion was built with Blender 4.3.2 and Pillow 11.1 with WebP support.
Refresh the output file sizes and
checksums in `sources.json` after conversion.
