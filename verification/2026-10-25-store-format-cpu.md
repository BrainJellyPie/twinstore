# Separate store layout selection on the CPU model

Date: 2026-10-25. Qwen3.5-0.8B Q4_K_M with the F16 vision projector,
llama.cpp b11878, CPU only, five threads, 8192-token context. These form
examples use the model's text path; earlier shelf probes exercise its image path.
Every run has a fresh application cache. Persistent server prefix reuse means
these times are observations, not benchmarks.

The production setup helper on main `00fd9a22` left a neighborhood bookshop
without a starting format and classified a Korean pharmacy as a convenience
store. The latter description explicitly said pharmacy, Saturday/Sunday 10–18,
and Seoul/Mapo. Its generated rationale invented a different schedule.

The helper now makes a second, compact format-only request. The wire grammar
requires exactly one listed format ID, and the prompt lists IDs, names and
business types without lengthy template descriptions. The selected format is
resolved through the existing ID/name parser; the second task cannot replace
names, descriptions, addresses, schedules or currencies from the first task.
Legacy null/omitted format fields remain parseable. A terminal typed output
truncation permits one 160-to-320-token expansion; unrelated errors do not.
This adds a model request, not a latency optimization.

The original facts schema and prompt remain unchanged. Broader experimental
facts rewrites recovered the supplied Korean hours and locations, but invented
hours, location or currency for the unspecified English bookshop. A five-task
variant even invented a street address. Those rewrites were withheld.

Actual production results, under `/workspace/scratch/cpu-vlm-probe/`:

| Case | Result directory | Calls | Seconds | Format | Other fields |
| --- | --- | ---: | ---: | --- | --- |
| Bookshop, unspecified details | `setup-unspecified-1792966310852370525` | 2 | 19.28 | bookstore / books | Hours, address and currency remain unset; name/description still invent campus |
| Weekend pharmacy | `setup-pharmacy-1792966333261518041` | 2 | 20.84 | drugstore / pharmacy | Supplied hours, days, location and currency missing |
| Night-only convenience store | `setup-night-1792966357130191970` | 2 | 11.79 | convenience | Missing days, location and overnight warning |
| 24-hour convenience store | `setup-24h-1792966371843161876` | 2 | 10.06 | convenience | Missing hours, days and location |

All four format checks pass, but **all four full fact checks still fail**.
The probe saves separate `format_ok` and `facts_ok` values, and exits nonzero for
any remaining issue. It checks the actual returned type, a known template,
opening hours/days, currency, given location and invented campus details.
A valid JSON answer alone is not treated as success. Wrong rationale text and
other possible inventions still require direct inspection beyond these checks.

The original bookshop (`setup-unspecified-original-1792965469501605042`)
already invented campus text and left other fields unset; the original pharmacy
(`setup-pharmacy-1792964491280094982`) chose `urban_cvs` and omitted its schedule.
The raw request/response traces and final drafts are retained without credentials.
There were no paid calls and no saved user-store changes.

Reproduce against a running local CPU server:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py \
  --case setup-pharmacy --output /tmp/twinstore-local-probes
```

Also available: `setup-unspecified`, `setup-night`, `setup-24h`. Ten targeted
format/fact-preservation and bounded-recovery regressions fail on the old helper.
Focused backend verification passes 225 tests, strict typing with zero errors
or warnings, and backend boot. Four existing LiteLLM cleanup warnings occurred.
The report-header integration passes 11 focused frontend tests.

The working main advanced to `eae6207b` during this cycle. Its palette search,
last-store links, report headings and release-note changes are preserved.

The additional palette integration passes 60 focused tests (71 frontend tests
including the report checks), TypeScript, changed-file lint with no errors or
warnings, and the frontend build (19.81 seconds; existing chunk-size warnings).
