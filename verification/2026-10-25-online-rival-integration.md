# Integrate rival visits and playback without cross-catalog ID confusion

Merged feature branch a33d1e0f (rival shops, GIF exports, animated visits and
side-by-side playback), preserving main's later interview and capture fixes.
The separate v0.5.0 release was observed published at 2026-10-25T13:44:50Z,
tagging f1edf64e; these new features and fixes remain Unreleased.

The rival matcher trusted local product/category IDs across catalogs. In the
bundled grocery/quick-commerce pair, p009 is Onions 3pk in one store and Cola
1.5L in the other. The lost shopper could be treated as specifically wanting
cola, contaminating the rival visit and attributed lost revenue.

Rival matching now receives the original store snapshot. It checks SKU, or
product name and category identity, before using an exact product; category-only
missions resolve the original category name. Unavailable exact products still
use the feature's existing smart-search alternative, and unrelated catalogs
with no match receive no visit. Both simulation and replay use this mapping.
Goal, budget, shopper identity and paired random draws are preserved.

The new 20-case integration matrix reproduced 12 failures with eight controls
passing in 2.91 seconds. It covers reused IDs, moved products/categories,
renamed products retaining SKU, missing products/categories, absent search
terms, generic bargain hunters, and stores with internal search disabled.
An upstream test itself assumed equal IDs meant equal products; it now chooses
a product actually sold by name in both catalogs.

Validation: 100 distinct backend checks pass. The initial focused run had
99 passes and that incorrect upstream identity assertion failing (26.07s);
the corrected three-test rival file passed in 0.73s. Coverage includes rival
reports/API, GIF/playback, eyesight, cross-catalog intent, short model failure
and interview lifecycle. Frontend: 87 tests passed in 14.95s; TypeScript,
changed-file ESLint and production build passed (19.06s build, existing large
chunk/plugin timing warnings). Full backend Pyright reported zero errors and
warnings; boot passed. No paid inference or model downloads were used.
