# Stop repeating SDK debug dumps in local JSON corrections

The actual three-person customer failure from 415 exposed a separate
harness issue. Instructor already puts each failed response into the
conversation as an assistant message, but its next user correction also
embeds the complete `ModelResponse` representation for every failed
attempt, including token usage, timing and transport metadata. Correction
messages grew from 4,944 to 8,661 characters in just two retries, repeating
information already available in the conversation and consuming a small
local model's context.

For loopback providers in JSON mode, the client now records the current
plain parsing/validation error before Instructor enriches it, then uses
that error in the SDK's next correction message. Only an appended user
message with the SDK's recognized correction prefix is changed. The
original user input, images, previous assistant replies and previous
corrections remain. Native-schema and remote-provider requests retain
their established correction format. First requests and cache identities
are unchanged. Retry limits, error objects, failed-attempt diagnostics and
usage accounting are unchanged; no response is fabricated or accepted
without validation.

## Actual CPU continuation and its limits

Qwen3.5-2B Q4_K_M, mmproj F16, llama.cpp b11878, five CPU threads, no GPU,
8,192-token context and reasoning disabled. The customer-writer sampling
temperature is **1**. The recorded first answer has all three customers
but omits their `purpose` fields. The continuation explicitly replays
that one historical response, then sends **two new HTTP requests** to the
actual CPU model. The replay is not counted as new inference. There are
zero application-cache hits.

| Correction input | Parent trace | Final code |
| --- | ---: | ---: |
| First correction message, characters | 4,944 | 733 |
| Second correction message, characters | 8,661 | 300 |
| Input tokens across the two actual correction requests | 11,156 | 5,933 |

The final code reduces these correction input tokens by **46.8%**. Its
initial request equals the parent's decoded request object exactly. All
three final request objects also equal the minimal prototype's requests.
Full attempt diagnostics still contain the recorded replies after failure.

**Both live correction replies still echo schemas, and zero customers are
accepted.** This is a context-efficiency fix with bounded safe failure,
not a successful repair of the model's schema-copying behavior. A separate
prototype adding an explicit data-instance reminder fails too and is
withheld. The final continuation takes 55.58 seconds, including 55.426
seconds for its two live calls. The historical parent takes 90.924 seconds
for those calls; these observations are not a latency benchmark because
server prefix-cache state differs. The final client usage total includes
the replayed answer's original tokens, as explicitly marked in its result.

A separate fresh JSON run at temperature 1 writes two bookstore customers
in 32.85 seconds with one actual HTTP request, no replay and zero cache
hits. Count, uniqueness, exact category labels and budget bounds pass.
Manual review still finds a Saturday-morning description in a Monday
fixture, so this is not a complete narrative-quality pass.

The historical duplicate-description reply from 405 is also replayed once,
followed by two actual CPU corrections at temperature 1 using the final
production hooks. Both still duplicate `description`; the run safely
rejects all answers and accepts no customers in 54.52 seconds. Repeated
duplicate-key repair remains a model limitation.

While comparing those records, an audit found that the 413 duplicate-key
report incorrectly described its new runs as temperature 1. Its saved
baseline, final and continuation request/result artifacts all show 0;
only the older 405 response being replayed came from temperature 1. That
report is corrected in this commit. The new 417 runs explicitly pass
`--temperature 1`; the old inference is not relabelled or counted again.

## Regression checks

The first 32 HTTP-boundary cases yield eight failures on the parent and
24 passing remote/native controls. All 32 pass after the change. The final
file has 64 cases covering synchronous/asynchronous text and image calls,
two wire modes, loopback/remote endpoints, validation/duplicate-key errors,
successful and exhausted retries, full final diagnostics, unchanged user
text that imitates the correction prefix, preserved assistant replies,
cache reuse and token accounting.

The focused suite passes **1,316 tests across 37 files in 22.55 seconds**,
with 111 existing LiteLLM asynchronous logging-cleanup warnings. Strict
Pyright has zero errors/warnings; boot and diff checks pass. Frontend code
is unchanged, inheriting 416's 55 UI tests and type/build/lint checks.
Released v0.8.2 artifacts and notes are unchanged; no release is created.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:
- Historical parent: `persona-hour-validator/persona-hour-identities-json-1793051988356519051`.
- Minimal prototype: `reask-compact-replay/persona-hour-identities-json-1793052548965665877`.
- Withheld reminder: `reask-instance-replay/persona-hour-identities-json-1793052655976963583`.
- Final production hooks: `reask-production-replay/persona-hour-identities-json-1793052963793967707`.
- Fresh temperature-1 control: `reask-production-fresh/persona-category-labels-json-1793053058098491005`.
- Duplicate-key continuation: `reask-production-duplicate/persona-category-labels-json-1793053195919473536`.

Continuation script: `/workspace/scratch/probe_compact_customer_reask.py`.
Request/token comparison: `/workspace/scratch/reask-compact-comparison.json`.
Logs: `/workspace/scratch/reask-compact-{before,core,tests,pyright-final,boot}.log`,
`reask-{compact,instance,production}-replay.log`, `reask-production-{fresh,duplicate}.log`.
Focused list: `/workspace/scratch/reask-compact-test-files.json`.
