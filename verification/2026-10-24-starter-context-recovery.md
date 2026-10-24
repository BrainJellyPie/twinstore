# Recover catalog context-window failures

The earlier bounded-task recovery handled invalid model replies, but not
`litellm.ContextWindowExceededError`. Large catalog requests could therefore stop
before any reply and never reach recovery. Instructor's retry wrapper also hid
this specific error from the selector.

Classify direct context-window errors and the final recorded context-window error
inside `InstructorRetryException` as a task-size failure. Category and product
selection then use the existing bounded recovery. Unrelated bad requests,
connection/configuration failures and authentication errors keep propagating.
If a bounded task itself exceeds context, stop with context-specific guidance.
No partial selection is returned or saved, and recovery is not recursive.

Offline discovery used the actual Instructor JSON-schema message preparation and
Qwen3.5-0.8B's tokenizer (public tokenizer.json, SHA-256
`5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`).
These are text-token counts, excluding chat-template framing and output tokens:

| Request | Tokens |
| --- | ---: |
| 100 ordinary shelf rows, category selection | 6,909 |
| 100 rows with long Korean names, category selection | 15,119 |
| Eight long-name rows in bounded recovery | 3,610–3,615 |
| Product selection for sixteen catalog categories | 11,897 |

Those requests can exceed the 4K/8K per-request budgets of managed local plans.
This measurement is input tokenization, not a live inference benchmark or an
observed success rate on a user's GPU. No model weights or paid calls were used.

Verification: the new reproduction had eight failures and two rejection controls
passing before the fix. Afterward, 111 focused selection/recovery/API checks passed
in 6.26 seconds, including the real Instructor wrapper around a mocked LiteLLM
transport, direct/wrapped errors at either stage, exact coverage of 100 shelves,
bounded failure and unchanged unrelated-error handling. Strict Pyright on the
changed production module reported zero errors; `git diff --check` passed.
