# Actual CPU decisions: valid JSON can still choose the wrong action

2026-10-26, Qwen3.5-0.8B Q4_K_M with the F16 vision projector, CPU only,
five threads, llama.cpp b11878, 8K context. The application source is based on
`24aac8a7`. Model responses and purchase choices are not mocked. All raw
requests, replies, rendered images and result files remain under the local
`/workspace/scratch/cpu-vlm-probe` directory; no weights or customer data are
committed. Times below include model calls but may benefit from the server's
warm prompt cache. They are observations, not latency benchmarks.

## Entrance variants withheld

The full-visit harness runs entrance planning, rendered shelf judgments,
checkout and shared stock through the application. It checks the entrance
list separately: a later impulse purchase must not conceal an omitted plan.
These scratch variants were tested against the same real examples:

| Variant | One unit, two shoppers | Browse only | Unavailable-only intent | Free item | Plans disabled |
| --- | --- | --- | --- | --- | --- |
| Explicit buy/browse/leave, root union | Pass | Pass | Enters incorrectly | Empty plan | Pass |
| Nested visit union, mission/reason first | Pass | Turns away | Invents laptop purchase | Pass | Not run |
| Original fields, compact schema and required list | Empty plans | Not run | Enters incorrectly | Empty plan | Not run |
| Separate visit choice then purchase list | Turns both away | Turns away | Pass | Turns away | Not run |

The root union binds a buy decision to at least one item and browse/leave to
an empty list. The nested variant keeps an object at the schema root and
moves that union under `visit`, writing mission/reason first. It also explains
that free items can be planned purchases. The compact variant removes schema
titles/defaults and requires mission, enter and items without changing the
original prompt. The two-stage variant first makes a text-only visit choice
from the same shopper and directory; only a buy choice would request a list.
All four two-stage cases choose leave, so no list call occurs. This does not
establish that its second stage works.

Representative artifacts:

- `visit-stock-one-decision-union-json_schema-1792979500225355022`: four
  calls, 18.70 s, two actual planned purchases, one sold unit and one lost unit.
- `visit-unavailable-decision-union-json_schema-1792979529463485274`: one
  call, 4.96 s. Decision is browse while the reason says it is not entering.
- `visit-free-decision-union-json_schema-1792980107108989021`: two calls,
  12.63 s. One free impulse purchase, but the entrance list is empty.
- `visit-plan-disabled-decision-union-json_schema-1792980122179338149`:
  two calls, 12.78 s. Empty plan and one permitted impulse purchase. This
  prototype's zero-cap prompt still contains “1 to 0”; its result is not
  evidence that the wording is suitable to ship.
- `visit-browse-decision-nested-json_schema-1792980191163190724`: one call,
  5.02 s; the browse customer is turned away.
- `visit-unavailable-decision-nested-json_schema-1792980198462047177`:
  one call, 5.70 s; invents category/product Laptop despite a water-only shop.
  The application does not resolve or buy that unavailable item.
- `visit-free-decision-nested-json_schema-1792980206562227000`: two calls,
  13.93 s; correctly plans and buys one free unit.
- `visit-stock-one-compact-schema-json_schema-1792980286512855188`: four
  calls, 16.22 s; both lists are empty, and one impulse purchase masks that
  failure if only receipts are inspected.
- `visit-stock-one-two-stage-json_schema-1792980426076082938`: two calls,
  2.69 s; both shoppers leave before seeing a shelf.

None of these variants replaces the production entrance model or prompt.
They solve selected examples while breaking others. In particular, a valid
decision/list combination does not prove that it follows the shopper's intent.

## Checkout failure and diagnostic correction

`local-shopper-probe.py` now supports both `json` and `json_schema`, with the
device and mode included in artifact names. The fixture shows a real rendered
checkout for a $19.99 item to a shopper whose explicit budget is $1.00.

The unmodified policy in plain JSON mode produces:

- `browse-budget-desktop-json-1792980573045189959`: one call, 8.46 s,
  chooses Place order and acknowledges the $19.99 cost.
- `browse-budget-mobile-json-1792980584599076129`: one call, 7.54 s,
  also chooses Place order, while its thought says it cannot afford the order
  and will close the tab. The saved screenshot was inspected: its order total
  and Place order button are visible.

Both are successfully parsed model responses, not rule-policy fallbacks.
Previously the diagnostic printed `unaffordable_order_avoided: false` but
exited with status zero. It now records `success: false` and an explicit issue,
and exits nonzero for an omitted budget, a fallback or an over-budget order.
A fresh CPU run, `browse-budget-desktop-json-1792980683755977164`, reproduces
the wrong order in one call (2.28 s) and correctly exits with status 1.

This fixes the diagnostic's false-success status, not the model's purchase
behavior. A passing probe still does not establish that all narrative text
agrees with the selected control; the raw thought remains available for review.

## Wrapped browser choices: production parser fix

A further scratch experiment writes the thought before the option and requires
that thought on the wire. The production prompt and wire schema remain unchanged;
this experiment is not shipped. In plain JSON mode, both desktop and mobile
responses put actual values under a single `properties` object. The old
`PageChoice` rejects them as missing `option`, so the rule policy supplies the
action. Its apparent budget-safe result is therefore not a successful VLM choice.

- `browse-budget-thought-first-desktop-json-1792980793154585828`: one call,
  8.33 s; actual option 9, rejected and replaced by rule-policy leave.
- `browse-budget-thought-first-mobile-json-1792980804526932307`: one call,
  6.97 s; actual option 1, also rejected and replaced by rule-policy leave.

The production change accepts those instance values through the original field
and page validators. It unwraps exactly one level, only if no root choice fields
are present. It never reads defaults/enums from a schema, guesses a choice from
the thought, or bypasses the valid-number and required-search checks. Canonical
cache results remain flat, and the production wire schema is unchanged.

Fresh CPU executions of the same experimental prompt after the parser fix:

- `browse-budget-thought-first-mobile-json-1792980994669866826`: one call,
  6.95 s; the same wrapped option 1 is now a model-sourced leave action, with no
  parser error or rule fallback.
- `browse-budget-thought-first-desktop-json-1792981035279887057`: one call,
  8.75 s; wrapped option 9 becomes the model's actual Place order action. The
  probe correctly fails because it exceeds the explicit budget. The parser
  exposes this semantic failure instead of masking it behind a fallback.

The thought-first schema-mode trials avoided the order on both screens but
invented details about the visitor/session. Along with the JSON-mode over-budget
choice, that is insufficient evidence to change production prompting.

## Integration and checks

Fast-forwarded the worktrees to main `24aac8a7`, which includes the upstream
customer share bars and View detail button. This is a main-branch integration,
not a claim that the prepared v0.8.0 release has been published.

Before the parser change, the new focused suite reports 10 failures and 24
passes. Afterward, 266 affected backend tests pass (20.21 s), including the
real LiteLLM/Instructor parsing path in both output modes, text/image calls,
search/leave controls, flat cache replay, invalid wrapped values, root-field
precedence and the captured CPU replies. Pyright reports zero errors/warnings,
and the server import smoke check passes. The affected UI suites have 21
passing tests (8.50 s); TypeScript and changed-file lint pass. The production
frontend build passes (20.23 s), with the existing chunk-size and Babel-plugin
timing warnings. Probe compilation and whitespace checks pass. No full backend
suite was run.
