# Product photos in VLM shelf grids

Numbered VLM grids now include available product photos alongside names, prices and exact SKU marks.
Bundled photos, current project SKU uploads, reviewed immutable photos and shelf-lab package artwork
resolve locally. Missing or invalid photos retain text cards. The same resolver feeds simulation,
interviews, shelf previews, marketing comparisons and optimization. Dense grids wrap within labeled
shelf levels, and marks above 99 remain selectable. Another 32 photos bring the bundled total to 96.

Validation on 2026-10-22:

- Targeted model/renderer checks captured the actual image sent to a fake VLM and checked photo pixels,
  exact SKU selection, every bundled image, 0–100 products, 128–768 pixel widths, malformed/oversized
  files, EXIF orientation and transparency. API tests verified a new uploaded photo replaces the old
  photo in the actual shelf-preview response. Foreign-project paths do not resolve.
- Full backend: 17,597 passed, one skipped, three capture-benchmark failures. The benchmark's ground
  truth still used the old row spacing. Updated its geometry and retained synthetic color packages
  for its color oracle, then added narrow/multiblock geometry cases and reran the affected capture
  and shelf-lab checks: 52 passed, one skipped. This was a full run followed by focused fixes, not an
  uninterrupted full pass.
- Strict backend type checking: zero errors. Application boot passed.
- Full frontend: 3,939 passed in 222 files; build passed; lint retained 19 warnings and zero errors.
- Browser: automatic diner creation through real API/storage with controlled model/persona responses,
  all 32 new image endpoints, the actual VLM shelf-preview grid (photo plus text fallback), and realistic
  rendering with all six atlases passed without page errors. Screenshots were visually inspected.
- Distribution wheel includes the original six atlases and local image resolver modules.

No live model provider or paid simulation was invoked. Generated image originals remain preserved.
