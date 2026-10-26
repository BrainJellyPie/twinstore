# Changing output mode must change the model request

2026-10-26, based on main `cd3333ce`. Actual CPU model: Qwen3.5-0.8B Q4_K_M,
F16 vision projector, five CPU threads, llama.cpp b11878, 8K context. No model
responses or browser actions are mocked in the following measurements. Raw
requests/replies, screenshots and sessions are retained in the local
`/workspace/scratch/cpu-vlm-probe` directory.

## Actual reproduction

The original JSON-mode run
`online-session-unavailable-mobile-json-1792981428355411362` creates three
valid browser-choice cache entries: open a clothing category, search for a
laptop, leave. Its exit survey copies the schema on both the initial request
and the bounded truncation retry, so it has no usable survey response.

A fresh JSON Schema run of the same fixture,
`online-session-unavailable-mobile-json_schema-1792983060693729094`, instead
opens the cart and leaves, then produces a structurally valid survey. It takes
three actual HTTP calls, no application-cache hits and 18.28 seconds. The
survey gives satisfaction/ease/recommendation 1/1/0 and would_return=false.
The saved images were inspected: the first thought says it wants to close the
tab but selects the cart, and the survey generalizes about checkout after seeing
only the home page and an empty cart. Valid structure and a completed no-purchase
goal do not establish semantic accuracy.

Before the fix, running JSON Schema with the saved JSON cache yields
`online-session-unavailable-mobile-json_schema-1792983180773207584`: all
three JSON-mode browser choices are reused, with only one actual HTTP call
for the new survey (4.27 s). Thus changing output mode does not actually
re-evaluate already-cached behavior in that mode.

The shared LLM client hashes the model, endpoint, sampling, response schema
and original prompts before Instructor adds its mode-specific instructions
and response format. Its key omitted `structured_output`, even though JSON
and JSON Schema send different instructions and decoding constraints. This
affects structured operations beyond the online shopper.

## Fix and actual verification

The client now retains output mode when configured or rerouted and includes
it in structured-cache identity. No prompt, schema, sampling default, chosen
action or model-output parser changes. Existing cache files contain only the
validated result and cannot establish which mode produced it, so old keys are
not reused or deleted. Their first subsequent request needs a fresh response.

Using the same original JSON cache after the fix produces
`online-session-unavailable-mobile-json_schema-1792983356795597470`:
three actual HTTP calls, zero cache hits, 8.19 seconds. Actions and survey
match the fresh JSON Schema run. A subsequent same-mode cache replay,
`online-session-unavailable-mobile-json_schema-1792983443051813246`, makes
zero HTTP calls and reuses all three answers in 0.33 seconds. That last run
is explicitly a cache replay, not new model inference. The server's warm
prompt cache also affects observed times; they are not latency benchmarks.

`local-online-session-probe.py` now accepts an explicit `--cache-from` cache
directory and records it in the result. It copies that directory into the new
artifact before running, preserving the original cache while retaining replay
counts separately from actual HTTP calls.

## Survey-format experiments withheld

Before finding the cache collision, the actual JSON-mode survey was tested
with these scratch variants. None changes production survey behavior:

- Compact schema: a full new visit takes four calls and 37.86 s
  (`online-session-unavailable-compact-survey-mobile-json-1792982334261700839`).
  The smaller schema is still copied rather than answered.
- A final instruction explicitly requesting actual ratings: three saved
  browser choices are replayed; two actual survey calls take 18.19 s
  (`online-session-unavailable-survey-values-mobile-json-1792982625730745872`).
- Frustration/improvement first: three choices replayed, two actual survey
  calls, 19.41 s (`online-session-unavailable-survey-text-first-mobile-json-1792982700747224039`).
  The model writes narrative text inside schema defaults but provides no
  numerical measurements. Those defaults must not be interpreted as answers.
- One field per call: three choices replayed, the first score-only request
  copies its schema and hits the 80-token cap in 4.18 s
  (`online-session-unavailable-survey-fields-mobile-json-1792982942346137097`).
  Later fields are not requested after that failure; their behavior is untested.

The initial final-instruction trial reused the original cache directory
directly; it added no survey answer because validation failed. Subsequent
replays use copied caches. The production JSON-mode schema-copy failure and
the narratives' semantic problems remain unresolved by this cache fix.

## Focused checks

The new regression suite has 11 failures before the fix. It exercises both
mode-switch directions through the actual LiteLLM/Instructor SDK, synchronous
and asynchronous text/image methods, same-mode cache reuse, reconfiguration of
one client, and old cache files whose producing mode is unknown.

After the fix, 97 affected backend tests pass (2.88 s), including existing cache
I/O, provider rerouting and fallback-chain coverage. The run reports 15 LiteLLM
logging-cleanup warnings. Strict Pyright reports zero errors/warnings, and the
server import smoke check passes. Probe compilation and whitespace checks pass.
No frontend code changes, so the preceding loop's frontend checks were not
repeated; no full backend suite was run.
