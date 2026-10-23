# Remove repeated catalog work from shelf comparisons

The sample store has 224 distinct product names. A rival comparison without any category filter
still classified every one against 1,784 bilingual catalog products. The classification was discarded
when selecting the comparison assortment. Four such calls made an existing rival-pull test take
over a minute and also delayed the corresponding user action.

Skip category classification for unfiltered comparisons. For searches that do need the catalog,
cache normalized names by immutable category contents (at most 256 entries, no user query cache),
check exact/full or pack-size-omitted matches first in the original order, and use SequenceMatcher's
upper bounds to avoid computing losing scores. Similarity thresholds and category/price behavior
are unchanged; changed catalog contents receive a different normalization-cache key.

Focused evidence:

- Before: two work-boundary tests failed and 48 matching cases passed in 0.86s. The work tests detect
  repeated catalog normalization and category calculation whose result cannot be used.
- After: **87 passed, 7 deselected in 3.99s**, including the previously interrupted rival-pull API
  test, rival price/identity boundaries, original category/price cases and offline capture flow.
- Matching cases compare with the previous exhaustive algorithm across Unicode/fullwidth names,
  empty/punctuation inputs, missing or restricted categories, duplicates, reordered categories,
  ties and size omissions. No live model calls.
- Local before/after benchmark, identical inputs and outputs: 24 unfamiliar sample names
  **1.9452s → 1.1097s**; one uncategorized rival comparison **21.5059s → 0.0007s**. Full serialized
  comparison output and all 24 selected products/scores were equal. These are local measurements,
  not service-wide latency promises.
- Strict Pyright on both changed engine modules: **0 errors**.

No full suite, new dependency, frontend or release asset change.
