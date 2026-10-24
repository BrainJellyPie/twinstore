# Validate contextual vision choices before caching and voting

A vision response could report positive interest without selecting any product.
Unknown names or nonexistent badges also passed response validation. In an
ensemble, these responses counted as no-choice votes and reduced a valid
member's interest (8 became 4). Single-model and photo-panel paths could also
accept/cache contradictory measurements or discover invalid targets only later.

The model-only shelf response now requires a target for positive interest and
validates that its name or badge resolves in the current view. Raw photos still
require a name rather than a number alone. This happens before caching, within
the existing call budget. Valid name/number fallback and zero-interest no-choice
responses remain supported; internal ShelfGlance defaults are unchanged. The
prompt states that a positive score must identify the product causing it.

The first reproduction found 36 failures and 19 passing controls for positive
interest without a target (3.63 seconds). Expanding to unknown names and badges
exposed 18 more failures after the first correction, with 60 passing cases
(4.18 seconds). Scripted HTTP covers both JSON modes, single/vote routing,
missing/null/blank/defaulted targets, invalid names/numbers, legacy caches,
later recovery and cache hits. Photo comparisons cover render, tagged photo
and raw photo, preserving valid choices and explicit zero responses.

Final verification covers 174 distinct focused checks. The initial expanded run
passed 160 and flagged ten assertions that still expected late "invalid" results;
these now fail at response validation and are classified "error". After updating
those stage assertions, all 26 photo-panel/API checks passed in 3.70 seconds;
the other 148 checks had passed in the 6.02-second run. Counts, error exclusion,
agreement and valid interest scores remain asserted. Full source Pyright reported
zero errors and warnings. No native inference or paid model calls were used.
