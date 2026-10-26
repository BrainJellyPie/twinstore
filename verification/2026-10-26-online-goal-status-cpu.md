# Online probe success requires the fixture goal

The online-session diagnostic recorded `goal_completed: false` but exited
successfully whenever its JSON, survey and accounting checks were valid.
A previous actual 2B CPU purchase visit exposes this: it added the requested
T-shirt seven times, then left without an order. Its nine model choices and
survey were valid, so `technical_success` was true despite failing the
explicit one-item purchase goal.

The probe now records overall `success` and exits zero only when both
technical checks and the fixture goal pass. The separate fields remain
available. This does not change application shopper behavior, infer actions
from thoughts, force purchases or claim that successful goal completion
proves the accuracy of a model's narrative.

## Evidence

The full probe CLI was replayed with saved actual sessions at the session
boundary; HTTP was explicitly forbidden. Four before/after executions used
zero model requests:

| Saved actual visit | Before exit | After exit | Technical | Goal |
| --- | ---: | ---: | --- | --- |
| Prior T-shirt purchase failure | 0 | 1 | Pass | Fail |
| New unavailable-laptop visit | 0 | 0 | Pass | Pass |

The purchase record is
`online-session-purchase-desktop-json_schema-1792990873844785659`
under `/workspace/scratch/cpu-vlm-probe-2b/`. Its original 10 HTTP calls
and 202.27 seconds are historical evidence, not new inference in this cycle.
The audit reuses its session result; it does not replay browser transitions.

Two new actual CPU visits use Qwen3.5-2B Q4_K_M with mmproj F16,
llama.cpp b11878, five CPU threads, no GPU, 8,192-token context, disabled
reasoning, temperature zero, production mobile screenshots and session
transitions. Each makes three HTTP calls, zero application-cache hits and
two browser choices: search for laptop, then leave the empty results page.
No fallback or purchase occurs. The native result screenshot was inspected
and explicitly says there are no matching products.

- Native schema, before the diagnostic change: 37.13 seconds;
  `online-goal-baseline/online-session-unavailable-mobile-json_schema-1793049016222876251`.
- JSON, after the change: 43.97 seconds, overall success/exit zero;
  `online-goal-final/online-session-unavailable-mobile-json-1793049120106439028`.

Goal and format checks pass, but manual review finds remaining narrative
errors in the JSON run: the first thought says it will leave while the
selected action searches; the survey claims the site forced the tab closed
and left it on the homepage. The actual second page is empty search results
and the model selected Leave. These quality failures remain unresolved.
No production prompt experiment is adopted in this cycle.

Audit: `/workspace/scratch/audit_online_goal_cli.py`,
`online-goal-audit-results.json` and `online-goal-audit-{before,after}-{purchase,unavailable}.log`.
New inference logs: `/workspace/scratch/online-goal-{baseline,final}.log`.
Probe compilation and whitespace checks pass. The accompanying layout-rename
integration has its own application verification report.
