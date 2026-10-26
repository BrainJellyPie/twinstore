# Actual CPU shopper failures and withheld prompt experiments

2026-10-26, on main `faba583d`. Qwen3.5-0.8B Q4_K_M, F16 vision
projector, llama.cpp b11878, five CPU threads, 8K context. No production
prompt or parser change is made by these experiments. Artifacts below are
under `/workspace/scratch/cpu-vlm-probe`; every listed inference uses fresh
application caches. Server prefix caching can affect observed durations.

## Full screenshot visits

The original desktop buying case asks for exactly one Cotton T-Shirt,
maximum $50, with the product visibly priced at $19.99. The baseline searches
for it and leaves despite the correct first search result; see the preceding
survey-coverage report for the screenshot inspection.

Scratch variants use the production session and actual rendered screenshots:

| Experiment / artifact suffix | HTTP calls | Seconds | Observation |
| --- | ---: | ---: | --- |
| Grounding reminder / `grounded-purchase-desktop-json_schema-1792984964306547696` | 3 | 24.57 | Searches then leaves; claims 15 minutes elapsed when the prompt says 18 seconds. |
| Separate elapsed/allowance/remaining seconds / `time-facts-purchase-desktop-json_schema-1792985036642788115` | 9 | 80.32 | Adds the target to the cart, then wanders until the step limit; thoughts still contradict selected actions and load measurements. |
| Select a complete numbered option label / `labelled-options-purchase-desktop-json_schema-1792985224501152593` | 9 | 83.85 | Opens the correct product and adds it, then repeatedly adds an unrelated cap; no completed order. |

Full artifact names start with `online-session-`. The labelled-option
experiment validates the selected full label back to its exact visible
number; it does not infer an action from thought text. All three are
structurally valid, but none completes the requested purchase. None is
adopted. The baseline preceded the reading-time branch integration; these
experiments follow it, so elapsed-time differences are not attributed solely
to prompt wording.

## Survey structure versus survey meaning

The saved JSON-mode unavailable-laptop visit from
`online-session-unavailable-mobile-json-1792981428355411362` copied the
survey schema instead of supplying scores. Reusing its exact survey user
prompt for a **new** model call gives:

- Raw text with the production survey instructions and no appended schema:
  `survey-no-schema-1792985440873843203`, one call, 3.98 s, valid 1/1/0/false.
- A wire schema containing only `{"type":"object"}`, retaining the full
  Pydantic score/type validation:
  `survey-minimal-schema-1792985577067913716`, one call, 3.99 s, valid
  1/1/0/false, but invented rude and unhelpful staff.

These are new survey inference calls over saved visit metadata, not new
browser visits. The tiny model's schema-copying failure can be avoided in
this fixture; that does not establish the accuracy of the resulting survey.

A controlled positive comparison uses the production **RulePolicy**, not a
VLM, to complete a $19.99 T-shirt purchase in ten recorded steps. Its actual
thoughts include "Cotton T-Shirt looks right" and "Good price, good reviews.
Into the cart." The visit is saved in `rule-purchase-survey-control`.
New CPU survey calls over that record produce:

- Minimal wire schema: `survey-minimal-schema-1792985750916254999`, one
  call, 4.32 s; valid 1/1/0/false, claims it could not find what it wanted.
- Original full JSON Schema: `survey-recorded-facts-False-1792985942518337092`,
  one call, 3.70 s; 1/1/0/false, describes slow checkout and a failed coupon.
- Full schema with recorded thoughts and per-page load times added:
  `survey-recorded-facts-True-1792985954210482155`, one call, 4.87 s;
  1/1/0/false, still invents a complex multi-step checkout despite this
  fixture's one-page setting.

A purchase alone does not prove satisfaction, and these scores are not
compared to an invented correct score. The concern is unsupported narrative
claims despite additional evidence. Minimal-schema recovery and expanded
survey context are therefore withheld along with the browsing experiments.

## Harness

The full online-session and checkout probes now accept an explicit HTTP
loopback `--endpoint` and record it in their results, allowing the same
fixture to be run against separate local model servers. The default remains
port 8081. Non-loopback endpoints are rejected. This changes diagnostics only.
The full-session probe also no longer calls any nonempty order a completed
purchase goal: it requires the exact product, quantity one and a total within
the explicit budget. A missing exit survey can still fail technical checks
without denying an otherwise completed buying goal.

## Second CPU model

After the environment reconnected, the downloaded Qwen3.5-2B Q4_K_M and its
F16 projector were served on loopback port 8082 with the same llama.cpp build,
five CPU threads and 8K context. The 0.8B server was not restarted alongside it.

The checkout case uses byte-identical screenshots and identical HTTP request
bodies on both models, with JSON Schema and a $1 budget against a $19.99 order.
The 0.8B baseline `browse-budget-desktop-json_schema-1792986213914188221`
makes one call in 7.97 s and opens delivery help while saying it will close the
tab. The 2B run `browse-budget-desktop-json_schema-1792990790684674488`
under `/workspace/scratch/cpu-vlm-probe-2b` makes one call in 15.82 s and
selects Place order. It correctly fails the probe's explicit budget check.
The larger model is not treated as a quality fix, and no rule overrides its
choice to make the probe pass. These observed times are not benchmarks.

The subsequent full 2B visit,
`online-session-purchase-desktop-json_schema-1792990873844785659`, allows
12 decisions and takes ten actual HTTP calls, zero cache hits and 202.27 s.
It opens the target, adds it seven times, then leaves without an order. Its
thoughts repeatedly say it will close the tab or check the cart while its
selected control adds another item. The response structure is valid, but the
buying goal is not completed. The five short startup-state regressions ran
during part of this visit; its timing is an observation, not a benchmark.
