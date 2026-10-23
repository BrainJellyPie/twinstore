# Main integration and finite-stock returns

Integrated against `949d74e`, with ordinary merge commits for:

- `feat/store-scenarios` at `dc240d9`: 128 additional catalog photos and crop bounds,
  checkout priority when refills coincide, valid default crew in unstaffed plans,
  and visible zero-hour crew comparisons.
- `feat/operator-modules` at `45f40d0`: virtual-customer guidance in all six languages,
  visitor-count grammar and disabled-model recovery.

The merge retains main's weekday roster, crew tasks for 3D playback and timeline,
layout operations and complete localization catalogs. Conflicts arose from shared
changes with different histories; old branch snapshots did not replace current features.
Two catalog bindings omitted during the first conflict resolution were caught by
component tests and restored before the successful rerun.

## Reproduced failures and repairs

On main, the incoming crew regressions failed in all 14 cases (0.77 s):

- Eight same-time pick/refill-completion and checkout combinations reserved staff
  for a refill before the waiting checkout was processed. Refill dispatch now stays
  in the lower-priority crew event, preserving main's task traces and weekday duty.
- Six unstaffed-day plans returned `crew: 0` through unchecked model copying and
  failed validation when saved. Normalization keeps a positive default and explicit
  zero-staff hours.

A separate finite-inventory regression failed in 24 cases (0.27 s): a basket returned
following a shelf refill was truncated to shelf capacity, discarding actual units.
Excess units now go back to the product's finite backroom. Faces marked dry can be
refilled again, including other faces of the same SKU. Unlimited products retain
existing behavior; original shoppers remain unchanged.

The committed regression matrix covers shelf/backroom levels, partial/full/no
refill, shared/per-SKU backrooms, staff counts, returns on either side of a refill,
same-day/next-day sales without deliveries, reproducibility and cross-face wakeup.
All **162** new return checks passed (0.71 s). The initial scratch test used an
incorrect customer-field name; that harness error was fixed before recording the
24 inventory assertion failures.

## Validation

- Shared-store engine/API after branch integration: **434 passed**, 25.56 s.
- Operations component tests, including roster and zero-hour rows: **131 passed**,
  two files, 5.33 s.
- Operator guidance and affected layout/launcher tests: **196 passed**, eight files,
  11.73 s, after the catalog binding repair.
- Expanded shared-store engine suite before the final two cross-face cases:
  **542 passed**, 7.13 s; the final 162-case return subset includes those two cases.
- Backend strict type check: **zero errors/warnings**. App import: **OK, 237 routes**.
- Frontend build: passed, Vite 19.10 s; existing bundle-size/plugin-timing notices.
- Frontend lint: **zero errors, 19 existing warnings**.
- `generation-copy-browser.mjs`: all six languages at 390×844 and 1280×640 passed,
  with exact generation choices, failure/retry, escaped original diagnostics,
  explicit model-start only and original setup preservation. Korean mobile and
  French desktop screenshots were inspected.
- `template-description-i18n-browser.mjs`: all six languages passed the real
  disposable API workflow, checking all 82 description sources, mobile/desktop
  layouts, Unicode area settings, localized SVG exports and two-floor saves.
  Preview and saved racks/products match exactly, including photo URLs.
- Disposable real HTTP workflow: a rule-based preview produced a run; an all-zero
  crew schedule was planned, saved to its copied layout and replayed with an outcome
  identical to the returned plan. The original fixture was preserved.

- Full frontend suite: **4,479 passed across 261 files**, 271.83 s, exit 0.
  Existing jsdom `scrollTo` notices only.
- Wheel build: passed; all **82** source catalog atlases are present byte for byte.
- Additional seeded stress check: **200** mixed-arrival scenarios, varying crew,
  shelf/backroom levels, checkout duration, patience and refill duration/threshold,
  conserved all finite stock after later shoppers exhausted it.

The initial full backend run lost its execution session during environment reconnection,
with its log at 97% and its process defunct. No completion/exit record survived, so
that run is **incomplete**, not passed. The same unchanged source snapshot was
rechecked with a separate durable exit record: **26,126 passed, 1 skipped in
1,111.48 s (18:31), exit 0**. The skipped Grounding DINO integration check requires
the optional capture extra and explicit `PARASTORE_TEST_GDINO=1` download opt-in.
Browser generation/model-start responses were intercepted, and the API run used
only the rule-based engine. No live model calls or real user data were used.
