# Bound retained shelf photograph memory

The prior 256-entry cache retained full decoded shelf photographs. At the supported
2048×2048 size, Pillow RGB storage alone is about 16 MiB per image, so a count limit
could retain several GiB across shelves and completed runs.

The cache now bounds estimated retained memory to 64 MiB and still caps entries at
256, including absent results. Accounting includes four bytes per image pixel,
product-box tuples/floats and cache/key overhead. Small images share the available
budget; hits refresh eviction order. Eviction drops the cache reference without
closing images held by active renderers. Reads stay outside the cache mutex, and a
generation counter prevents an upload's invalidation from being undone by an older
in-flight decode.

Evidence:

- A separate process loaded 12 supported 2048×2048 JPEG/box pairs under an extra
  192 MiB address-space allowance. Before: `MemoryError` after ten images, peak RSS
  236.3 MiB, 0.206 seconds. After: all twelve loaded with dimensions and boxes intact,
  peak RSS 132.5 MiB, 0.176 seconds. Script/results are recorded in the local loop's
  scratch artifacts; no live providers were used.
- New regression checks before the fix: six failures and two passes in 0.69 seconds.
  Cases cover 64/512/2048-pixel images, metadata-heavy photos, LRU hits, live caller
  ownership, 200 small images, bounded missing results and upload during decode.
- After: 15 focused cache, shelf rendering and shelf-view API checks passed in
  10.58 seconds. Strict Pyright for the changed module and its application consumer
  reported zero errors or warnings.

The budget bounds cache retention, not the whole process or images still owned by
active rendering calls. Oversized individual entries are returned without caching.
