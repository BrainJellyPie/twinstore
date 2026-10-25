# Retain valid category selections during local-model recovery

Based on main `5f169922`, 2026-10-25. Actual Qwen3.5-0.8B Q4_K_M,
CPU only, five threads, llama.cpp b11878, 8192-token context, plain JSON mode.
No model replies are mocked in the CPU experiments and no user store is saved.

The preceding compact convenience-store run completed in 14 HTTP calls and
147.67 seconds (`compact-json-1792968704276235442`). Its primary product reply
contained usable selections, but one invalid category caused the entire answer
to be discarded. The complete correction echoed normalized long SKUs, exceeded
the model's context, and caused every category to be requested individually.

Product recovery now retains a category only when it occurs exactly once, is
requested, contains unique SKUs belonging to that category, and fits its count
and shelf-capacity limit. It asks smaller tasks only for the remaining categories.
It preserves the order and actual product choices of good groups. Duplicate
category groups are never retained. Unknown categories do not replace required
ones. Completely invalid or structurally unparseable responses keep the existing
bounded recovery. Every final category is validated again before a result is
returned; failed recovery produces no partial result or store mutation.

The scratch prototype (`compact-json-partial-1792969033640574840`) completed in
four HTTP 200 calls and 90.45 seconds: categories, products, dairy repair and
beer repair. Eight valid groups were reused. Both repaired categories returned
ten complete, valid, unique product codes against a cap of eight; the preceding
validated-subset recovery bounded those lists. All 12 physical target racks were
assigned and stocked. There were no oversized correction requests.

Timings are observations, not benchmarks: a persistent llama.cpp process can
reuse prompt prefixes. Completion and catalog validity do not establish that
the model's assortment preferences are realistic.

Reproduce with the committed production probe:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py \
  --case compact --structured-output json --output /tmp/twinstore-local-probes
```

The new regression cases cover missing and unknown categories, duplicate
categories, unknown/cross-category/duplicate SKUs, count overflow, fully invalid
and structurally invalid answers, recovery failure, and reuse of cached partial
responses. Valid groups deliberately choose the last catalog product, while
recovery chooses the first, to detect accidental reselection. The partial
recovery assertions failed in 23 cases before the implementation. Two existing
fallback cases already passed. A cache-test fixture signature was corrected
before rerunning that regression against the old implementation.

The production rerun `compact-json-1792969563236507270` also completed in four
HTTP 200 calls, 93.05 seconds. Its two smaller tasks addressed dairy and beer;
the other eight groups exactly preserved the primary reply's SKU choices and
order. Inspection of the saved store and responses confirmed 12 unique stocked
rack assignments, catalog membership, category limits, and no validation issues.

Focused verification covers 268 backend cases. Six SDK fixture cases initially
failed because their fake provider assumed every product request contained both
categories. After teaching that fixture the single-category request, all 22
keyed-response cases passed in both JSON modes; the other 246 cases had passed.
Backend strict typing reports zero errors and warnings, and the server boots.
The frontend's three affected suites pass 17 tests, TypeScript and changed-file
lint have no errors, and the production build completes in 20.58 seconds. The
existing root-route fast-refresh warning, bundle-size/plugin-timing warnings,
and six LiteLLM cleanup warnings remain.

This iteration also integrates upstream branch `532f8457`: off-page run notices,
mobile online browsing, physical-analyst channel facts, store-name validation,
and file-input styling. The earlier malformed layout-ID guard remains present.
