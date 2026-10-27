# Give impulse models exact product-face access coordinates

Real local-model visits browse the wrong side of a shelf or emit `[-1, 2]`,
an out-of-grid target. The impulse prompt shows each rack's first three
sorted surrounding tiles, without associating a tile or face with the
exposed product. A large rack can omit the actual product's access tile
entirely. The engine's later sanitation bounds the route, but cannot infer
the intended browse product from an unlabeled action.

Each R reference now identifies one rack/block/face, with an exact copyable
JSON `target` and `face` calculated using the existing geometry helper.
Repeated shelf levels share the same location; distinct blocks and faces
retain separate references. A placement with no walkable stance is marked
unavailable instead of advertising some other side. Catalog selection
remains coordinate-free. Offer codes, prices, exposure order, schemas and
route execution are unchanged.

## Real CPU evidence

Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads, no GPU, context 8192,
reasoning disabled and temperature zero. All final cases run real pattern,
intent and impulse calls through receipt execution, with three HTTP calls
per case and zero application cache hits.

| Case | Prior impulse browse | Final impulse browse | Final seconds |
| --- | --- | --- | ---: |
| Free tea / native | `[-1, 2]`, E | `[2, 1]`, N | 36.24 |
| Paid tea / JSON | `[1, 2]`, N (wrong side) | `[2, 1]`, N | 55.73 |
| Paid tea / rotated two-block shelf / native | New boundary case | `[3, 3]`, E, the second block's correct stance | 41.73 |

Each final impulse reply contains one browse action at the correct product
face. All purchase/receipt checks pass: one Green Tea, unchanged quantity
and total, one payment, exit, and no invalid purchase drop. In both paired
comparisons, the first two request bodies and replies are identical. The
impulse system prompt is also identical; only its user prompt's location
information changes. Timing is observational, not a speed claim.

The initial intent-stage browse still selects a wrong side in all three
cases. This change fixes the information supplied to the impulse stage;
it does not establish full-visit spatial correctness. The probe now reports
checked browse counts and location validity separately for each stage.
Its overall success flag remains a purchase/receipt check. Narration is not
scored and still includes speculative or imprecise content. The intent
stage's equivalent coordinate ambiguity is the next target.

## Regression checks and reproduction

The corrected pre-change fixture reproduces 36 failures and one pass.
An earlier test-only floor-blocking fixture used a nonexistent Store field;
that fixture was replaced with an internal shelf face before measuring the
baseline. The core geometry/catalog checks pass 109 tests in 6.10 seconds.
Final checks across ten related files pass 328 tests in 16.06 seconds,
without warnings. Strict Pyright reports zero errors and warnings; server
import, probe compilation and diff checks pass. Frontend checks are
inherited from integration 448.

Coverage includes four rotations, four faces, reversed slot order, repeated
levels, multiple blocks, boundary and occupied/internal access, exact offer
price on execution, and preservation of the selection prompt.

Use `verification/local-intent-probe.py --case one --mode json --full`;
add `--layout rotated --mode json_schema` for the rotated shelf case.
Actual requests/replies are in `/workspace/scratch/impulse-face-locations-final`
(`free-json_schema-1793076377515481019`, `one-json-1793076416284714795`)
and `impulse-face-locations-rotated/one-json_schema-1793076512194460043`.
Input/reply comparisons, logs and selected tests use the
`impulse-face-locations-` prefix. This is Unreleased; v0.8.2 notes and assets
are unchanged.
