# Automatic starter products: local-model recovery

The reported wizard failure omitted `section_0` while returning invented IDs such
as `section_10` and `section_999`. The existing complete-answer correction could
repeat the same error. A section's descriptive physical rack count also gave a
small model an opportunity to expand one supplied ID into nonexistent racks.

The main prompt now lists the exact expected IDs and explicitly distinguishes a
section from its member racks. Valid grouped responses still take two structured
calls overall. After a grouped selection fails validation and its one semantic
correction, category selection decomposes into batches of at most eight rows.
The model returns an ordered list of category choices, without resource IDs; code
binds it to the original rows. The bounded JSON schema includes actual catalog
enums and exact list lengths. Runtime validation also checks membership, the
shared sixteen-category budget and SKU uniqueness, including providers that do
not constrain their output with a grammar.

Failed grouped product selection decomposes by category. Each response can choose
only that category's SKUs, within its configured limit and shelf capacity. Neither
recovery path silently substitutes format defaults or returns partial results.
Schema/JSON/truncated-output failures can decompose immediately after the provider's
structured retry handling. Connection/configuration failures, including connection
errors wrapped by Instructor, propagate without extra catalog calls. Small tasks
have at most one semantic correction; the existing 100-row/16-category limits
bound decomposition. Recovery can therefore add calls for a weak model.

Offline evidence:

- Before the change, the new reproduction suite had 23 failures and four rejection
  controls passing. Twenty-one failures repeated the reported invented-ID pattern
  at 1, 2, 8, 9, 16, 99 and 100 rows in USD/KRW/JPY. The other two showed that
  execution never reached the intended recovery-stage provider-error controls.
- Related engine and API checks passed: 937 in 26.19 seconds. These cover existing
  catalog/template combinations, normal two-call responses, exclusions, prices,
  source-change protection, full project creation and no partial project on failure.
- Seven additional cases cover malformed/truncated/wrapped errors, the category
  budget across batches with unusual exact IDs, and cache reuse of repaired output.
  The final focused recovery rerun passed 101 checks in 5.33 seconds (including
  those seven); 944 distinct checks passed across the two successful runs.
- Strict Pyright on the changed production module: zero errors. `git diff --check`
  is clean. No frontend strings or data format changes.

The tests replay failed replies through fake clients and the real LiteLLM cache
adapter, plus the real create-store API. No live or paid model calls were made.
These establish recovery and validation behavior, not a measured success rate for
the user's local model or the semantic suitability of its category choices.
