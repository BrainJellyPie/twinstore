# Exercise the customer writer with an actual twelve-person request

The ordinary `persona-nightmarket` probe caps generation at twelve customers,
but its real traffic-estimation stage returned one visitor. That run passed
the checked KRW 3,000–10,000 budget, category and 23:00 arrival conditions;
it did not exercise a twelve-person batch.

The new `persona-nightmarket-batch` case supplies twelve observed customers
to production `generate_personas_for_day`. It isolates the writer from the
trade-area and traffic estimators, using two supplied customer types and the
same Korean customer description. The result explicitly names this scope
and fails if twelve independently written records are not returned. No model
response is mocked; the actual request/response and cache usage are retained.

Qwen3.5-2B Q4_K_M ran on llama.cpp b11878, five CPU threads, no GPU and an
8,192-token context. Each request used native `json_schema` and fresh
application caches. The fixed-cohort wire schema had minItems=maxItems=12.

| Actual run | HTTP calls | App cache hits | Outcome | Time |
| --- | ---: | ---: | --- | ---: |
| Full nightmarket pipeline | 3 | 0 | One written customer; checked fields pass | 37.16 s |
| Fixed twelve-person writer, production prompt | 1 | 0 | Twelve distinct records, but two minimum budgets are 2,000 instead of at least 3,000 | 106.49 s |
| Fixed writer, scratch-only explicit budget-copy prompt | 1 | 0 | All budgets match 3,000–10,000, but four records duplicate earlier profiles exactly | 95.10 s |

The last prototype asks the model to copy the supplied range without changing
it for age, gender, job or personality. That run trades the budget failure
for repeated people, so the prompt was **withheld**. No production prompt,
batch size, budget adjustment or deduplication behavior changed. This is a
new reproducible failing boundary, not a claim that these model limitations
are fixed. Server prefix reuse was possible; timings are not a speed study.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `persona-nightmarket-fresh/persona-nightmarket-json_schema-1793017408290437828`
- `persona-nightmarket-batch-fresh/persona-nightmarket-batch-json_schema-1793017536912165783`
- `persona-budget-copy-diagnostic/persona-nightmarket-batch-json_schema-1793018037847353997`

The scratch runner is `/workspace/scratch/probe-persona-budget-copy.py`.
The repository change is limited to the verification harness and this record.
Probe compilation and diff checking passed. Already-green application tests
were not repeated for unchanged production code. The v0.8.2 tag is unchanged.
