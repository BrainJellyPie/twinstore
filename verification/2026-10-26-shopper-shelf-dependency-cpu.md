# Keep a generated shelf-purchase condition from disappearing

Qwen3.5-2B Q4_K_M, running in llama.cpp b11878 with five CPU threads and no
GPU, returns `bought_there: "no"` without `stopped_at` for a request to find
visitors who bought nothing at the Tea shelf but may have bought elsewhere.
The previous application accepted and cached that filter, then omitted its
shelf-purchase condition entirely. The same reply also contains unrequested
persona/time constraints. These are separate defects; this change addresses
the missing dependency, not all of the model's interpretation errors.

`find_shoppers` now validates that a non-`any` `bought_there` has at least one
shelf resolvable against the actual product racks. It uses the same name
resolution and rack-ID groups as matching, including duplicate display names.
Missing, blank, unknown-only and ambiguous targets request correction before
caching. Bounded failures retain diagnostics and are not cached. A mixture of
known and unknown alternatives preserves the known target and existing warning.
Searches with no shelf-purchase condition and direct legacy `apply_filter`
behavior retain their existing semantics. No guessed shelf is inserted.

## Controlled regression evidence

Before the fix, **48 dependency cases fail and 11 compatibility cases pass**
in 4.24 seconds. After the fix, eight shopper-search engine/API files pass
**467 tests in 12.44 seconds**, with 103 existing dependency/resource warnings.
Four additional ambiguity, mixed-target and duplicate-name cases are included
in the final focused file check: **63 tests pass in 3.85 seconds**, with 15
existing warnings. This covers 471 distinct focused cases across the two runs.
The tests exercise both JSON modes, bounded failure, corrected replies, stale
cache validation, known-name resolution, store/customer immutability, and
unrestricted searches. Strict Pyright has zero errors or warnings; application
import, probe compilation and diff checks pass. Frontend code is unchanged
and inherits integration 420's 150 focused tests and successful build/typecheck.

## Actual CPU observations and limits

All calls below use temperature 0, a fresh application cache, 900 output tokens,
context 8192 and `http://127.0.0.1:8082/v1`. No HTTP reply is mocked or replayed.
These are text requests to the local VLM, not image-reading or real-shopper
experiments. The seven fixture customers include full personas, paid/free
purchases, nonbuyers and arrivals on either side of a seconds boundary.

- Parent native-schema shelf-only request: **7.68 seconds, one HTTP request**;
  the missing shelf condition is silently omitted.
- Final native-schema shelf-only request: **25.30 seconds, two HTTP requests**.
  Both actual model replies omit the target. Validation stops the search with
  a bounded error and writes no response-cache file. The initial request and
  reply are exactly equal to the parent run, establishing the changed handling
  of the same real output. **This is successful rejection, not model repair.**
- Parent JSON shelf-only request: **21.98 seconds, one request**. It supplies
  the shelf but adds unrequested and contradictory filters. The final JSON
  request behaves the same (**23.30 seconds, one request**).
- Final JSON known-product request (**10.70 seconds, one request**) invents
  persona, spending and visit-duration constraints and finds nobody.
- Final JSON exact-arrival request (**8.49 seconds, one request**) changes
  15:00:30 to 15:00 and adds a product-purchase condition. It fails the intended
  customer-group check. These semantic failures remain unresolved.

The new `local-filter-probe.py` checks both matched IDs and applied conditions.
An empty result for an unrelated reason cannot pass an unavailable-product
case. Its nonzero exits for these final runs explicitly record quality failures.

Two prompt candidates are withheld. A concise field guide removes some
invented demographic constraints but reverses the shelf nonpurchase condition,
drops an arrival bound and adds unrelated product conditions. Four fresh native
cases are saved under `shopper-filter-cpu-candidate`. Its free-purchase case
matches the expected IDs but adds extra constraints, so it is not a semantic
pass. A neutral JSON starting template also reverses the shelf condition in
one fresh native call (11.57 seconds). An initial template-escaping mistake
caused four prototype invocations to fail before HTTP; these are harness
errors, not model runs, and the corrected actual call is saved separately.
Neither candidate changes the production prompt.

The first exploratory seven cases used no persona records. They exposed
unrequested model fields but cannot establish realistic matching quality.
Four parent cases were then rerun with all seven complete personas and still
failed. The unavailable-product case's initial ID-only "success" is explicitly
not a semantic pass: unrelated restrictions happened to return zero rows.

## Artifacts

- Parent populated native cases: `/workspace/scratch/shopper-filter-cpu-populated/`.
- Parent JSON: `shopper-shelf-cpu-parent/shelf-only-json-1793056135598231043/`
  (use the directory under `/workspace/scratch/shopper-shelf-cpu-parent/`).
- Final native: `shopper-shelf-cpu-final/shelf-only-json_schema-1793056159918265403/`.
- Final JSON: `shopper-shelf-cpu-final/shelf-only-json-1793056187720366792/`,
  `known-json-1793056213299141022/`, `precision-json-1793056226399182440/`.
- Comparison: `/workspace/scratch/shopper-shelf-reproduction.json`.
- Withheld guide/template: `/workspace/scratch/shopper-filter-candidate-v1.txt`,
  `shopper-filter-candidate.txt`, `shopper-filter-cpu-candidate/`, and
  `shopper-filter-cpu-neutral-valid/`.
- Test/check logs and exit summaries: `/workspace/scratch/shopper-shelf-*`.
