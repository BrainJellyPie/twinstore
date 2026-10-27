# Reject copied schemas before creating or caching blank receipts

## Observed bug and fix

With Qwen3.5-0.8B in plain JSON mode, the free-product receipt returns a complete
JSON Schema (`$defs`, `properties`, `required`, `title`, `type`) instead of
observed values. The old parser ignores those keys and fills every optional
field with defaults: no products, no date/time and no total. That blank receipt
is **cached as a successful model result**. The 1400-token diagnostic completes
normally in 32.40s with 875 output tokens, so this is not just truncation.

The receipt validator now rejects schema metadata objects that contain no
recognized receipt fields before defaulting or caching. Instructor can retry
them as invalid answers. Genuine/legacy partial receipt data, an empty legacy
object, and real values accompanied by harmless schema annotations remain
readable. Extra metadata is not added to the normalized receipt cache.

The user message explicitly asks for values read from the photo, not schema
keys. Besides clarifying the request, this changes the prompt cache identity,
so the old prompt's normalized blank records are not reused for new reads.
No existing cache files are deleted and no schema-compression policy changes.

## Actual CPU results and limitations

Qwen3.5 Q4_K_M with F16 vision projectors, llama.cpp b11878, five CPU threads,
zero GPU layers, context 8192, 512 image tokens, reasoning disabled and
temperature/seed zero. 0.8B uses port 8081; 2B uses 8082. Nine completed runs,
ten HTTP requests/attempts, no application cache hits.

| Run | Seconds | HTTP | Outcome |
| --- | ---: | ---: | --- |
| 0.8B JSON baseline, diagnostic cap 1400 | 32.40 | 1 | Copies schema; blank receipt incorrectly cached |
| Data-request clarification alone, cap 1400 | 27.40 | 1 | Same wrong blank result/cache |
| Final guard, 0.8B JSON, normal 6144 budget | 57.95 | 2 | Both schema echoes rejected; **zero cache entries** |
| Exploratory compact-schema prompt, cap 1400 | 45.69 | 1 | Still copies/expands schema and truncates; withheld |
| Final guard, 0.8B native, free products | 8.47 | 1 | Pass: both products and zero amounts/total retained |
| Final guard, 0.8B native, cancelled transaction | 5.26 | 1 | No product rows, but printed zero total becomes null |
| Unchanged main 460, same cancelled fixture | 5.08 | 1 | Same zero-total error; not introduced by this change |
| Final guard, 2B JSON, fractional return | 15.57 | 1 | Pass: negative quantity/amount retained, CSV blocked |
| Final guard, 2B native, date without time | 17.32 | 1 | Pass: no invented time, review still requires correction |

**This fixes false acceptance and caching; it does not make the 0.8B plain-JSON
transcription succeed.** Its full-budget run still fails after two schema echoes,
now with a validation error and no cached blank result. Native schema remains
the validated default local-provider path. The cancelled-receipt zero-total
limitation also remains: both old and new 0.8B runs copy `TOTAL\n0.00` into the
evidence field but return numeric total null. Both correctly keep the product
list empty and block sales export. Synthetic fixtures do not establish general
photo accuracy.

Run index: `/workspace/scratch/receipt-schema-echo-run-index.json`. It includes
exact directories, cases, modes, source hashes, replies and cache-entry counts.
The inference-stage guard source hash is
`3d483358979955d2c6e4ece6eb408eb8716094ce9ee8e7eceaf96885d1cdc903`.
A final `cast(object, value)` resolves strict typing after the dictionary check
without changing the returned object. Final source hash:
`701eab0fcb3ce12aa02901df70c167af20b4a5ec4a88a7271f9a0fa5f5fce1b7`.
Schema, system prompt and user-message constants are verified identical before
and after that typing-only change. No inference is repeated for the cast.

## Focused verification

The new tests fail nine checks and pass one compatibility check before the fix
(2.42s). The implementation passes 403 tests in 19 receipt/currency engine and
server suites (11.26s, 113 existing LiteLLM logging warnings). They cover schema
fragments/full echoes, valid values plus annotations, legacy partial data,
retried corrections, repeated failures without cache entries, and valid cached
reuse in both output modes. After the typing-only correction, all ten new tests
pass again in 2.44s, strict Pyright has zero errors/warnings and server import
prints OK. Diff checks pass. Frontend validation is inherited from integration
460; no UI source changes here. v0.8.2 and older changelog bytes, release tags and
assets remain unchanged. Check logs use `/workspace/scratch/receipt-schema-echo-`.
