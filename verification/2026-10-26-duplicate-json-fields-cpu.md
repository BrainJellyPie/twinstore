# Reject duplicate JSON fields before they overwrite model data

An audit of 1,791 saved response strings in 864 CPU trace files found seven
parseable replies with repeated object keys. Six were older 0.8B schema echoes
with repeated `type` annotations. The seventh, a real 2B JSON customer reply,
contained two different `description` values per customer: a full customer
profile followed by a copy of `behavior_tendency`. Parsing silently kept the
second description. The previously reported narrative-copying symptom in
405 therefore also involved a concrete parser data-loss bug.

The structured-response parser now checks object pairs before Pydantic
collapses them. A repeated key raises a JSON parsing error inside Instructor's
normal bounded correction loop, preserving failed-attempt token accounting.
This covers both wire modes and synchronous/asynchronous text/image calls.
The guard retains the original response schema, documentation and validators;
normal text inside strings and distinct objects with the same field names
are unaffected. Identical repeated keys are rejected too. Thinking/example
text is removed by the existing final-answer handler before this check.

Corrupt raw cache entries are ignored. The parser cache version changes
from `final-think-v2` to `unique-json-v3`: old canonicalized cache entries
cannot prove whether earlier values were overwritten, so they are bypassed
without deletion. Existing saved customers are not rewritten.

## Actual CPU observations and the repair limit

Qwen3.5-2B Q4_K_M, mmproj F16, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, reasoning disabled. The fresh baseline/final
requests and the two live correction requests in this report used
temperature **0**. The historical duplicate reply from 405 was generated
at temperature **1**, which is the default customer-writer setting.
The previous version of this paragraph incorrectly labelled this cycle's
new requests as temperature 1; their saved request/result artifacts were
audited and this description corrected during cycle 417. These runs alone
do not test the production sampling setting.
The fixture has two fixed customer identities and two supplied categories.
Times are observations; server prompt-prefix caching may vary.

The historical duplicate reply is under
`/workspace/scratch/cpu-vlm-probe-2b/persona-category-final/persona-category-labels-json-1793046180726528653/`.
It was actually generated in cycle 405; this cycle does not count that old
inference again. A new baseline JSON call is duplicate-free, writes two
customers and meets the budget/category checks in 28.24 seconds with one
HTTP request and zero application-cache hits. The defect is not claimed to
reproduce on every identical request.

A targeted continuation replays that exact historical response as the first
answer, then sends the parser's two correction requests to the actual CPU
model. Both real correction replies still repeat `description`. All three
answers are rejected, no customers are accepted, and no response cache file
is written. This is safe rejection, **not successful model repair**.
The run takes 77.32 seconds: one recorded reply plus **two new HTTP calls**
of 34.345 and 42.819 seconds. The live calls consume 8,894 prompt and 1,076
completion tokens. The probe's aggregate three-request usage additionally
includes the replayed response; its result explicitly labels replay versus
actual calls. No attempt is made to guess which description the model meant.

Fresh final runs with the guard both pass automated count, uniqueness,
category and budget checks, each with one actual HTTP request and zero
application-cache hits:

| Wire mode | Seconds | Written customers | Outcome |
| --- | ---: | ---: | --- |
| JSON | 17.91 | 2 | Unique descriptions, separate behavior fields |
| Native schema | 22.10 | 2 | Unique descriptions, separate behavior fields |

These do not establish general customer quality or repair the known arbitrary
budget-following limitation. Manual review of the native run finds an
unsupported book-borrowing intention in a bookstore fixture. No semantic
budget values or invented replacement profiles are forced into the output.

## Regression evidence

All first 32 new HTTP-boundary cases fail on the parent, then pass with the
guard. The final file has 45 cases covering corrected/repeated/escaped/identical
keys, nested/root objects, bounded retries, all four call interfaces, both
wire modes, usage counts, cached responses, corrupted cache content, quoted
JSON, thinking/fences, real wire-schema equality and existing validation.

The first broader run has 1,219 passes and three expected cache-identity test
failures: those fixtures hard-coded the previous parser version. Their
updated matrix checks both old-parser invalidation and same-parser cache
reuse, independently of schema-prompt compaction. The final focused run
passes **1,225 tests across 35 files in 21.09 seconds**, with 111 existing
LiteLLM asynchronous logging-cleanup warnings. Strict Pyright has zero
errors/warnings; boot and diff checks pass. No full suite is rerun.
Frontend code is unchanged, inheriting 412's 83 UI tests and type/lint/build
checks. Released notes and v0.8.2 remain unchanged.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:
- `json-duplicate-baseline/persona-category-labels-json-1793049608216519051`
- `json-duplicate-repair/persona-category-labels-json-1793049946657424733`
- `json-duplicate-final/persona-category-labels-json-1793050079893165909`
- `json-duplicate-final/persona-category-labels-json_schema-1793050100640937975`

Audit and continuation scripts/results:
`/workspace/scratch/audit_model_duplicate_keys.py`, `model-duplicate-key-audit.json`,
`replay_duplicate_customer_repair.py`.
Logs: `/workspace/scratch/json-duplicate-{baseline,before,core-tests,repair,final-cpu,tests,tests-final,pyright,boot}.log`.
Focused list: `/workspace/scratch/json-duplicate-test-files.json`.
