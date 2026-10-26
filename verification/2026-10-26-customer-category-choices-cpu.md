# Keep listed customer preferences tied to real departments

On main `43c80521`, customer identity and purpose were constrained to the
supplied vocabulary, but preferred_categories remained free strings even
when a department list was supplied. Unknown, blank or partly valid lists
could survive generation and cache reuse. Targeted regressions reproduced
21 failures with seven existing valid cases passing before the repair.

The customer wire schema now offers the exact supplied department labels
as inline string enums. Response and cache validation reject unknown or
translated labels, allowing the existing bounded model correction path to
repair them. Exact names, including whitespace and Unicode, are preserved;
only unambiguous surrounding-whitespace/case variants are normalized.
Empty preferences remain valid for browsing. With no supplied list, the
existing category-inference behavior is unchanged. No budget values,
persona descriptions or customer counts are synthesized or clamped.

## Verification

All 28 targeted cases pass after the repair. They cover native-schema and
JSON wire contracts, corrected/persistently invalid replies, corrupted
cache records, unknown tail entries, empty/browsing preferences, exact and
ambiguous case variants, duplicate input labels and no-list inference.
The wire-contract assertions were added after the pre-fix run; that run
already exposed the acceptance/normalization failures themselves.

Broader focused verification passes 582 backend cases across 20 files in
33.62 seconds. This includes customer label/budget validation, preferences
reaching the planner, generation context, sample/batch IDs, truncation and
context recovery, concurrent generation and the identity API. Thirteen
existing LiteLLM asynchronous-logging cleanup warnings remain. Strict
Pyright reports zero errors/warnings; server boot, probe compilation and
diff checks pass. Frontend code is unchanged, inheriting the preceding
78 Area tests and TypeScript/lint/build. Released changelog text and the
v0.8.2 tag/assets remain unchanged.

## Actual CPU checks and limits

The new `persona-category-labels` fixture calls the actual production
customer writer for a fixed two-person cohort, with supplied department
names `Books — 새책·헌책` and `Stationery / 紙もの 🌿`. It does not claim to
exercise upstream area/traffic estimation. Qwen3.5-2B Q4_K_M runs on five
CPU threads, no GPU, llama.cpp b11878, 8,192-token context and disabled
reasoning. Temperature is **1**, matching the default customer writer.
Each run uses one actual HTTP request, a fresh application cache and no
application cache hits.

| Application | Mode | Seconds | Category result | Broader result |
| --- | --- | ---: | --- | --- |
| Baseline | Native schema | 18.26 | Exact supplied labels | Budget failure |
| Repaired | Native schema | 13.82 | Exact supplied labels | Same budget failure |
| Repaired | JSON | 34.15 | Exact supplied labels | Automated checks pass |

The baseline already copied these labels correctly; this CPU fixture is
not presented as a reproduction of an unknown category. The deterministic
validation/cache regressions reproduce that gap. Native output before and
after the change keeps the same two people and budgets: one starts at
2,000 KRW despite a supplied 3,000–10,000 KRW range. The native probe remains
failed; this semantic budget issue is unresolved. JSON output keeps both
budgets within that range. Manual review also found that each JSON persona
repeats its behavior text as its description, which the existing automated
text checks do not flag. This change does not claim to repair narrative
quality or arbitrary free-text budget interpretation.

Evidence under `/workspace/scratch/cpu-vlm-probe-2b/`:
- `persona-category-baseline/persona-category-labels-json_schema-1793045998868380992`.
- `persona-category-final/persona-category-labels-json_schema-1793046164047660838`.
- `persona-category-final/persona-category-labels-json-1793046180726528653`.

Logs: `/workspace/scratch/persona-category-{baseline,before,core-tests,final-cpu,tests,pyright,boot}.log`.
The focused test file list is `/workspace/scratch/persona-category-test-files.json`.
