# Fractional customer budgets and schema-echo corrections

This diagnostic extends the customer writer probe with
`persona-fractional-batch`: two fixed local residents at 09:00 in Lyon,
coffee/bakery categories, and a French description specifying a per-visit
budget of **€2.50–€7.75**. It exercises the production writer directly,
without upstream profile or traffic generation. The production parser,
prompts, schema, retry behavior and money conversion are unchanged.

All completed live calls used Qwen3.5-2B Q4_K_M on llama.cpp b11878,
five CPU threads, no GPU, 8,192 context, reasoning disabled, temperature
**1**, and fresh application caches. The following are selected diagnostic
runs, not a model-accuracy benchmark.

| Run | Seconds | Completed live HTTP calls | Outcome |
| --- | ---: | ---: | --- |
| Production JSON | 112.46 | 3 | Copied the exact supplied JSON schema twice; then wrote two customers, one with €1–€3 instead of the requested range |
| Production JSON Schema | 18.65 | 1 | Wrote two customers, but one upper budget was €8 instead of at most €7.75 |
| Scratch reask candidate, fresh JSON | 27.67 | 1 | Both budgets correct, but the reask candidate was never invoked |
| Scratch reask candidate, assisted diagnostic | 62.86 | 2, plus one replay | First correction put schema definitions inside `personas`; the next wrote two customers, one with a €9.50 upper limit |

The candidate removes failed schema-only assistant messages from the retry
history and explicitly requests customer instances. It lives only in
`/workspace/scratch/probe_schema_echo_reask.py` and is **withheld**. Its
fresh successful run used the exact same first request as the production
JSON failure, but received a different first response after the environment
and model server restarted. Since no retry occurred, that success cannot
be attributed to the candidate.

The assisted diagnostic explicitly reuses the recorded first schema reply
from the production failure. It asserts that the initial request is equal,
then makes two actual model correction calls. Its probe counter/usage
includes the replay; do not count it as three fresh HTTP calls. The observed
failure is why no retry-policy change is being shipped.

There were **three completed fresh runs with five HTTP calls**, plus the
assisted run's **two live correction calls**. Every application cache-hit
count was zero. A separate initial candidate attempt was interrupted when
the execution environment reconnected: its request had started, but no HTTP
reply or result was recorded. That interrupted attempt is excluded from
the completed-run counts and is not classified as a model failure.

The successful model amounts were decimal strings with dots and converted
to cents correctly. This experiment therefore supplies no evidence for
relaxing decimal-comma or numeric-float parsing. The remaining failures are
schema copying and source-budget interpretation. The previously committed
blank/zero unspecified-budget correction remains in place; it does not
alter these nonzero amounts or enforce natural-language budget ranges.

Reproduce with `verification/local-model-probe.py --case
persona-fractional-batch --temperature 1 --structured-output json` (or
`json_schema`) and `--endpoint http://127.0.0.1:8082/v1`. Raw inputs,
request/reply bodies, returned customers and results are under:

- `/workspace/scratch/customer-fractional-budget/`: production JSON
  `1793064159183412072`; native schema `1793064704928422899`.
- `/workspace/scratch/customer-schema-reask-candidate/`: fresh completed
  `1793064524676033217`; interrupted `1793064371267192958`, with an explicit
  `interruption.json` and no completed result.
- `/workspace/scratch/customer-schema-reask-replay/`: assisted
  `1793064606360978078`; runner `probe_schema_echo_replay.py` and scope
  metadata `customer-schema-reask-replay-scope.json` in the scratch root.

The combined summary is `customer-fractional-probe-summary.json` in that
scratch root. Probe compilation and diff checks passed. Production source
is unchanged from `537fcb70`, which passed 529 related tests, strict Pyright
and backend boot checks. Those checks were not rerun for this probe/report
addition. No release files or published tags/assets changed.
