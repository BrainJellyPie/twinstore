# Infeasible starter prices remain an unresolved semantic failure

On main `39e3bbc0`, a real CPU bookstore run requested only books priced
100–200 USD inclusive. The catalog contains eight books priced 9.99–34.99
USD, so none can satisfy the request. The application nevertheless selected
and placed a 14.99 USD book. Correct category IDs, product IDs and counts
were insufficient to establish that the request was honored.

The reusable `book-price-unavailable` probe now exercises this condition.
It verifies that the catalog actually has no eligible book (so later catalog
changes cannot silently invalidate the fixture), then fails any selected
book outside the requested range. The diagnostic does not classify a generic
exception or a partially stocked store as successful refusal. A replay of
the baseline cache fails with the same result in 0.01 seconds, zero HTTP
requests and two application cache hits. This replay is not another inference.

## Rejected candidates

All trials use Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads,
no GPU, an 8,192-token context, disabled reasoning and temperature zero.
Every fresh run uses two actual HTTP requests and zero application cache
hits; llama.cpp may reuse an input prefix. Times are observations, not
benchmarks. This is a text task using a vision-capable model.

| Revision | Mode | Seconds | Book selected |
| --- | --- | ---: | ---: |
| Unmodified application baseline | Native schema | 25.71 | 14.99 USD |
| Explicit @NONE choice and refusal handling | Native schema | 9.35 | 19.99 USD |
| Explicit filtering and a no-match example | Native schema | 9.20 | 19.99 USD |
| Requirements after catalog; generic no-match example | Native schema | 9.18 | 14.99 USD |
| Same reordered candidate | JSON | 32.08 | 14.99 USD |
| Empty-list refusal instead of @NONE | Native schema | 23.98 | 14.99 USD |
| Same empty-list candidate | JSON | 33.56 | 14.99 USD |

All seven runs fail the requested price condition. The explicit-filter
trial initially used the fixture's prices as its prompt example; even that
failed. Later candidates used an independent 40–50 USD example with
10/20 USD candidates. The JSON runs sometimes copied an entire candidate
list; existing bounded-subset normalization reduced valid IDs to the
requested count but could not establish semantic eligibility.

None of the candidate prompt, schema, sentinel, exception or input-order
changes is retained. Backend application/test code is byte-identical to
main `39e3bbc0`. No claim is made that infeasible assortment requests are
fixed. The earlier feasible price-range improvements remain intact.

Evidence is under `/workspace/scratch/cpu-vlm-probe-2b/` in
`starter-unavailable-{baseline,candidate,filter,task-last,empty,audit}/`.
Each fresh run preserves request/reply bodies, source/stocked stores and
its semantic result. The two final candidate source snapshots are
`/workspace/scratch/starter-unavailable-{sentinel,empty}-candidate.py`.
The committed probe compiles and its baseline replay fails as expected.
No backend suite is rerun for this diagnostic-only change.

## Follow-up: extracting price constraints before selecting products

On 2026-10-27, the unchanged production probe again selects an out-of-range
book for the impossible 100–200 USD condition: two real requests, 23.46
seconds, no application cache hits. The baseline is under
`/workspace/scratch/starter-infeasible-baseline/`.

A separate scratch experiment asks the same CPU model to extract per-product
lower and upper limits for books and stationery before any catalog selection.
The source quote is checked against the supplied text. Four schema variants
and a final boundary expansion use 24 fresh requests, one per case, with
the same 2B model, CPU settings and temperature zero described above.
They do not modify the production selection path or stock any store.

| Extraction schema | Cases / checks passed | Observed limitation |
| --- | --- | --- |
| Decimal strings, empty string for no limit | 4 / 0 | Omits explicit limits; treats a shopping budget as per-product limits. |
| Nullable numbers | 4 / 3 | Reads Korean 25,000–28,000 won as 25–28 won. |
| Nullable strings restricted to source number tokens | 4 / 1 | Returns null limits despite explicit price ranges. |
| Nullable numbers restricted to amounts from the source | 4 / 4 | Initial English and Korean cases pass their specific checks. |
| Same numeric enumeration, expanded boundaries | 8 / 7 | A Korean total shopping budget becomes a book-price limit despite an explicit statement that there is no per-product limit. |

The expanded cases also cover different limits for two categories, removal of
an old restriction, discount percentages, quantities, an upper-only bound,
Japanese yen and unrelated opening hours. These selected-case counts are not
accuracy estimates. Restricting numeric output prevents the observed
thousand-fold magnitude error, but does not establish that the model applied
the number to the correct concept. Deterministic catalog filtering on the
incorrect Korean budget interpretation would exclude valid products.

All extraction candidates remain **withheld**. No automatic price filtering,
extra production model call or prompt change is introduced. Infeasible
assortment requirements remain an unresolved semantic failure. The separate
captured-ID fix on main `3b51ce36` does not address this limitation.

Artifacts and scratch scripts use `/workspace/scratch/starter-price-extraction*`
and `probe_starter_price_extraction*.py`; aggregate paths and request counts
are recorded in `starter-price-extraction-summary.json`. The final boundary
run ends in `1793072816446227266`. This follow-up changes only this report;
backend verification is inherited from main `3b51ce36` and frontend
verification from integration 434. The published v0.8.2 files are unchanged.
