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
