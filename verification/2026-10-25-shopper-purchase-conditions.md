# Combined shopper purchase conditions — 2026-10-25

When a generated filter said both bought=no and bought_there=no on a named shelf,
the executor discarded the whole-trip condition. It included shoppers who bought
at another shelf and advised asking for an empty basket, although that same
combination could not express the requested constraint. The executor now applies
both predicates with AND. The schema and prompt distinguish whole-trip purchase
status from a shelf-only condition (bought=any). Shelf-only searches still include
shoppers who bought elsewhere. The old API assertion for widening was corrected.

Baseline: 4 failures, 32 passes in 3.24s. The failure included both paid and free
purchases elsewhere in the supposedly empty-basket group. All 398 focused cases
passed after the fix in 8.44s: native Ollama/OpenAI, JSON/JSON-schema, all nine
whole-trip/shelf combinations, nonvisitors, free purchases, cache reuse, unchanged
input records, existing spelling/range/clock filters and the search API. Full
backend Pyright: 0 errors, 0 warnings; server boot passed. No live inference;
existing SDK logging cleanup warnings remain.
