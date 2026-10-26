# Budget experiments withheld after a sparse-input regression

2026-10-26, after main `502a62f9`, Qwen3.5-2B Q4_K_M on CPU,
llama.cpp b11878, five threads, no GPU layers, 8K context. The supplied
per-person budget still disappears on later customers in some batches.
The following are diagnostic experiments, not a new budget-repair policy.

Writing one person per request improved the two previously failing cases.
The French EUR 2.50–7.75 case retained 250–775 stored units on both people.
It used two saved upstream results and three actual customer HTTP calls:
one JSON-mode response echoed the schema, and the existing bounded retry
returned a real customer. Total 87.23 s. The Japanese JPY 500–1,500 case
retained 500–1,500 on both people, with two upstream hits and two actual
JSON Schema customer calls, 23.83 s. These are not fresh full-pipeline timing
benchmarks, and not evidence that the narratives are fully consistent with
the requested day/hour. The French result still calls a Monday visit a
weekend morning, for example.

A new counterexample supplied only `동네 주민` (neighborhood residents),
with no budget. A fresh four-call, one-person-per-request JSON Schema run
completed in 45.81 s but invented a 3,000–10,000 KRW budget for the second
person. With the exact same upstream profile and traffic copied into a
new cache, the original two-person batch returned 0–0 for both in one new
15.016-second call (15.15 s total). The probe correctly failed the single-
person run and passed the paired control on budget checks. The tentative
application change from five people per request to one was therefore
reverted, together with its test expectation. Production local pacing
remains five; the test that showed the tentative policy difference is not
claimed as a regression fix.

Two further Japanese two-person experiments also remain unshipped:

- Asking for budgets before narrative fields, with an explicit instruction
  not to infer them from prices, occupations or intent: one fresh call,
  20.33 s total, second budget still 0–0.
- The same prompt plus moving the schema properties and required keys to
  put budgets first: one fresh call, 14.89 s total. The actual JSON did put
  budgets first, but the second budget was still 0–0.

The verification CLI now supports `--persona-batch-size 1` through `12`
for controlled comparisons and adds `--case persona-unspecified`. Its
budget check distinguishes a supplied range from a genuinely unspecified
budget; it does not fill budgets or change any generated values.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `single-person-persona-fractional-json-1792993596716314104`
- `single-person-persona-local-categories-json_schema-1792993820419246027`
- `persona-unspecified-json_schema-1792993950710998032` (single, fresh)
- `persona-unspecified-json_schema-1792994122582875439` (paired control)
- `budget-first-persona-local-categories-json_schema-1792994252672558953`
- `budget-first-schema-persona-local-categories-json_schema-1792994456987653817`

The remaining budget preservation problem is explicit and unresolved.
Neither zero budgets nor positive budgets are automatically correct merely
because the JSON parses. No values were overwritten to make a test pass.
