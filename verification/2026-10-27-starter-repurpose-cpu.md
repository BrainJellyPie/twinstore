# Actual CPU checks: override a bookstore's shelf purposes

Run the existing `book-repurpose` probe on production engine code from main
`a6016ff9af753575d2786c95bf5daeffea419e8b` (unchanged since the earlier receipt
fix). Qwen3.5-2B Q4_K_M, llama.cpp b11878, CPU only, five threads, 8192 context,
reasoning disabled, temperature zero. The application uses the real loopback
provider with a fresh cache; model replies are not mocked.

The 8×6 USD bookstore starts with books and stationery shelf purposes, while
the explicit requirement replaces every section with `gift_wrapping` and
allows at most two products. This checks whether the default shelf purposes
incorrectly override the user's requested change.

| Output mode | Seconds | HTTP requests / attempts | Result |
| --- | ---: | ---: | --- |
| Native JSON schema | 23.33 | 2 / 2 | Pass |
| JSON | 30.30 | 2 / 2 | Pass |

Both assign all four eligible racks exactly once to gift wrapping, select
two catalog SKUs and place only those SKUs across 80 product placements.
The input layout is unchanged, exclusions and limits hold, and every placed
product retains its catalog identity and price. Both runs have zero application
cache hits. No production prompt or selection change was needed for this case.
This is a specific instruction-following check, not a guarantee for arbitrary
assortment requirements or natural-language budgets.

Artifacts under `/workspace/scratch/starter-repurpose-cpu/`:

- `book-repurpose-json_schema-1793082955456466418`
- `book-repurpose-json-1793083014547822085`

Each contains the source/stocked store, exact requests, raw replies and results.
