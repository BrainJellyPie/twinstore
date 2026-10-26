# Preserve customer types within their requested hours

Customer batches may span several arrival hours. The writer previously
validated `identity` against the trade area's global list, then assigned
arrival hours by array position. A globally valid response could therefore
put a retiree into a student-only morning cohort without any correction.
All first 12 intercepted-HTTP cases reproduce this on the parent, in both
JSON modes, with one-person and mixed-hour batches, repeated errors and
corrupted response caches.

The batch validator now checks each retained row against its original
hour's supplied customer types before response caching. A mismatch reaches
Instructor's existing three-attempt correction path. The original prompt
and global grammar are unchanged; the new cross-row check runs after label normalization.
No identity is silently rewritten to fit an hour. Existing short responses,
discarded surplus rows and bounded truncation/context recovery remain.
This check concerns independently written customers, not a new guarantee
about population sampling, copied customers or free-text narrative quality.

## Actual CPU observations

Qwen3.5-2B Q4_K_M, mmproj F16, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, reasoning disabled. A fixed observed cohort
requests one student at 09:00, one retiree at 13:00 and one night shift
worker at 21:00 in a single three-person batch. This directly exercises
the writer, without upstream traffic estimates changing the fixture.
All runs have fresh application caches and zero cache hits. Times are
observations, not performance comparisons; a type check overlapped part
of the baseline's third attempt.

| Version / mode | Temperature | HTTP calls | Seconds | Result |
| --- | ---: | ---: | ---: | --- |
| Parent / JSON, deterministic control | 0 | 1 | 35.78 | All three hour/type and budget checks pass |
| Parent / JSON, production sampling | 1 | 3 | 175.35 | Hour/type checks pass; two budgets violate the supplied range |
| Withheld extra prompt sentence / native schema | 1 | 1 | 33.01 | All three hour/type, category and budget checks pass |
| Withheld extra prompt sentence / JSON | 1 | 1 | 31.38 | Hour/type checks pass; all three budgets are incorrectly 3–5 KRW |
| Final validator, original prompt / native schema | 1 | 1 | 33.14 | Hour/type checks pass; budgets fall below the requested minimum |
| Final validator, original prompt / JSON | 1 | 3 | 126.64 | Missing purposes, then two schema echoes; zero customers accepted |

The baseline's first production-sampling reply omits all `purpose` fields.
The second echoes the JSON schema instead of customers. The third has
structurally valid customers, but two budgets remain outside 3,000–10,000
KRW. The probe reports failure for this semantic budget issue. **The actual
CPU runs do not reproduce the hour/type swap**; that defect is established
by controlled HTTP replies. An additional hour-consistency prompt sentence
was tried, then withheld after its JSON run produced 3–5 KRW budgets. This
does not establish that the sentence alone caused the regression, but it
provided no reliable reason to change the established prompt. The final
implementation retains only validation. Arbitrary free-text budgets,
timing narratives and other model behavior remain unreliable; no inferred
budget is clamped or silently replaced to make a probe pass.
The final JSON run safely fails after three attempts; it is not successful
customer generation. Its initial HTTP request is byte-for-byte equivalent
as a decoded JSON object to the parent production-sampling request, including
messages and options. This validator does not change the initial prompt or
wire schema. These failures remain explicit limitations of the 2B model.

## Focused regression checks

The final new file has 27 cases: both wire modes, bounded correction,
repeated failure, cache revalidation/reuse, short/surplus handling, Unicode
and case normalization, interleaved requests and recursively split batches.
The first focused run reports 602 passes and seven failures in older
global-label fixtures: their hourly pool allowed only the first label,
while their mock writer deliberately cycled through the whole global list.
Those fixtures now supply all intended labels for that hour, retaining
their original global-enum and normalization assertions.

The focused run passes **609 tests across 21 files in 35.95 seconds**,
with 13 existing LiteLLM asynchronous logging-cleanup warnings. Strict
Pyright has zero errors/warnings; application boot, probe compilation and
diff checks pass. After restoring the original prompt, the 80 directly
affected hour/global-label/normalization cases pass again in 5.53 seconds.
Frontend code is unchanged, inheriting 412's 83 UI tests
and type/lint/build checks. No full release suite is repeated. The released
v0.8.2 tag, artifacts and changelog section are unchanged.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:
- `persona-hour-baseline/persona-hour-identities-json-1793051399014583609`
- `persona-hour-baseline-live/persona-hour-identities-json-1793051460040241579`
- `persona-hour-final/persona-hour-identities-json_schema-1793051659466781437`
- `persona-hour-final/persona-hour-identities-json-1793051817889991135`
- `persona-hour-validator/persona-hour-identities-json_schema-1793051906172863097`
- `persona-hour-validator/persona-hour-identities-json-1793051988356519051`

The two `persona-hour-final` artifacts are the withheld prompt candidate,
despite that directory's original name. `persona-hour-validator` contains
the final code with the original prompt restored.

Logs: `/workspace/scratch/persona-hour-{baseline,baseline-live,before,core,tests,tests-final,restored-tests,pyright,boot,final-native,final-json,validator-native,validator-json}.log`.
Focused list: `/workspace/scratch/persona-hour-test-files.json`.
