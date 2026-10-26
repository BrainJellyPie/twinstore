# Check actual placements after local-model assortment selection

On main `fa9a3c6e`, run the production initial-assortment pipeline with
Qwen3.5-2B Q4_K_M, llama.cpp b11878, CPU only, five threads, an 8,192-token
context and fresh application caches. No model replies were mocked.

The probe now saves the original store and checks that selection does not
mutate it. After placement, check unique rack assignments, excluded
categories, per-category product limits, selected versus placed SKU sets,
and each placed item's complete currency-specific catalog identity and
price. Record the selected/placed SKU counts and physical placements.
Geometry validation remains in place. These checks do not establish
market-price accuracy or the semantic suitability of every product.

| Case | Output mode | HTTP calls | Elapsed | Selected/placed SKUs | Placements |
| --- | --- | ---: | ---: | ---: | ---: |
| Japanese café/bakery, JPY, one product/category, no alcohol | JSON schema | 2 | 49.18 s | 9 / 9 | 96 |
| French neighborhood bookstore, USD, two products/category | JSON | 2 | 37.63 s | 4 / 4 | 80 |

Both completed with zero application-cache hits and no reported issues.
The café filled twelve racks. Its `water_sports` category means water and
sports drinks. The bookstore chose books and stationery across four
racks, then returned all eight valid product codes for each category
despite the requested limit of two. The existing bounded-subset repair
retained two valid unique choices per category without another model call.
This run confirms that repair and downstream placement; it introduces no
new production selection behavior. Prompt-prefix cache conditions were
not controlled, so elapsed times are observations, not benchmarks.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `cafe-json_schema-1793004105279906303`
- `book-json-1793004274859938061`

This integration also merges `6feabb3c` and its predecessors: model-backed
helpers show model readiness, dialogs restore focus to their opener,
removing an area venue stops map dragging, and areas without expected
visitors show an explanation. The affected 13 frontend test files passed
all 120 tests in 10.21 s; existing router-provider warnings were emitted.
Changed-source ESLint and TypeScript checking passed; the production build
passed in 20.19 s with chunk-size/plugin-time warnings. Probe compilation
and `git diff --check` passed. Backend application code is unchanged since
the preceding verified main commit, so backend tests and strict Pyright
were not repeated.
