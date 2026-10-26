# Customer field meanings and exact budget units on the CPU model

2026-10-26, starting from main `721dc2c7`. Actual Qwen3.5-0.8B Q4_K_M
requests on llama.cpp b11878, CPU only, five threads and an 8192-token
context. Sampling is temperature 0, seed 0, with thinking disabled. Each probe uses a fresh application cache. The persistent server may
reuse prefixes; observed times are not independent benchmarks.

The production `persona-cafe` case supplies a Japanese neighborhood café
profile, Tokyo, JPY, a 500–1500 yen budget, coffee/bakery preferences and one
Monday opening slot. The plain-JSON run
`persona-cafe-json-1792972641136748989` fails before generating any customers:
two HTTP 200 replies each exhaust 4096 output tokens (248.48 seconds total).
Both replies copy `$defs` and `properties`, then repeat the same Japanese
label hundreds of times. These are incomplete JSON replies, not usable
customer populations. The production exception is preserved in `result.json`.

A scratch prompt adds explicit instructions for the three keys and English
label arrays. `persona-cafe-instance-json-1792972961854047141` still exhausts
4096 tokens in its first reply (124.955 seconds), copying schema structure and
repeating `afternoon`. The probe was interrupted after saving that first reply
to avoid another duplicate attempt; it is not a completed workflow result.

Inlining the shared label constraint, with the same field bounds and added
prompt, also fails: `profile-shape-cafe-json-True-1792973093320048345` reaches
a deliberately smaller 1600-token exploratory ceiling while copying
`properties`/`items` and repeating labels. This isolated profile test is not a
4096-token production comparison. Neither prompt wording nor removing schema
references alone establishes a fix.

Further isolated trials use the same 1600-token exploratory ceiling and only
one completion each. None completed:

| Variant | Directory suffix | Seconds | Observation |
| --- | --- | ---: | --- |
| Inline schema plus user-message format reminder | `True-1792973148365093783` | 44.16 | Correct top-level keys, then repeats variants of “neighbor's partner” |
| Short English profile prompt, original label-count request | `False-1792973211231434756` | 45.77 | Copies schema and repeats keywords |
| Original Korean prompt reduced to 3–8 labels, user-message reminder | `False-1792973271560439833` | 47.40 | Still truncated |
| Reduced label count and explicit three-array answer shape | `False-1792973321756497871` | 45.49 | Still truncated |

Directory prefix for these rows is `profile-shape-cafe-json-`. These trials
were withheld. No truncated JSON is repaired into a fabricated profile, and
no production prompt/schema changes are justified by these failures. The local
llama.cpp provider's actual default is JSON Schema mode; the failing JSON mode
is a supported alternate configuration, not evidence that its default is JSON.

## The default grammar completes, but its fields still need inspection

The unchanged production JSON Schema run
`persona-cafe-json_schema-1792973378835638441` completes in three calls and
32.81 seconds, with two written customers and 150 total visitors after the
normal daily-sample expansion. Its numerical checks pass. Manual inspection
finds identities/purposes equal to “飲食店” (food shop) and “カフェ” (café),
Japanese narratives despite the English-output instruction, and an age range
used as walking behavior. The old probe's `success: true` therefore established
only numerical/structural completion, not sensible customer fields.

A shorter English profile prompt alone
(`persona-cafe-compact-json_schema-1792973435986804997`, three calls, 29.28
seconds) gives human identities, but still puts people labels into the purpose
pool and outputs Japanese narratives with `behavior_tendency: "10s"`. That
intermediate prompt was not shipped.

A candidate explicitly distinguishes PEOPLE from actions/needs in the profile,
and spells out the customer fields in concise English while retaining category,
currency, budget, label, ordering and individual-person requirements.
`persona-cafe-fields-json_schema-1792973582996036829` completes three calls in
24.26 seconds with appropriate English text, but writes two identical customers;
it was revised before adoption. The next candidate adds an explicit requirement
for distinct descriptions and plausible differences within a batch.
`persona-cafe-fields-distinct-json_schema-1792973672954075909` completes in three
calls and 24.31 seconds, with two different descriptions/demographics, human
identities, action purposes, English behavior and the supplied 500–1500 JPY
range. This is a narrow real-model result, not a population-calibration claim.

The probe now reports `population_ok` and `text_ok` separately. It flags fields
with no English words, exact identity/purpose equality, demographic-only behavior,
and identical independently written profiles. These are diagnostics for observed
mistakes, not a complete language/meaning classifier. Application schemas still
accept user labels and do not fabricate replacement customers. Existing copied
`twin_of` samples are excluded from the duplicate-written-profile check.

## A second major error: budgets 100 times too small

The probe now includes a French neighborhood bookstore (Lyon, EUR, books and
stationery, a stated €5–€20 budget) and a Spanish description of a US shop
(Austin, USD, snacks/drinks, a $3–$10 budget). These extend the existing Korean
KRW and Japanese JPY cases to currencies with fractional major units.

The French bookstore with the candidate field prompts but the original Korean
currency fragment returns `budget_min=5`, `budget_max=20` instead of 500 and
2000: `persona-bookstore-json_schema-1792973819584457994`, three calls, 29.35
seconds. Its diagnostic correctly fails. The original main prompts also fail
that same input: `persona-bookstore-old-json_schema-1792973883175326691`, three
calls, 32.94 seconds, again 5–20. Their person type is “librairie” and purpose
is “lundi”; a Latin-letter check alone cannot detect these French field mistakes.

An intermediate budget instruction explicitly states the conversion in English:
100 stored units per USD/EUR major unit; multiply the supplied major-unit amount
by 100. Existing zero-decimal currencies retain one stored unit per unit of
currency, with an explicit instruction not to multiply or divide them by 100.
This changes only the instruction supplied to the model, not prices, schemas,
saved customer records, rounding or the currency-unit conventions elsewhere.

That instruction-only variant also fails: `persona-bookstore-json_schema-1792973940440717004`
returns 100–200 instead of 500–2000 (three calls, 32.60 seconds). It was replaced
by a change to the generated response contract, not accepted as a fix.

The model now writes `budget_min_major` and `budget_max_major` as decimal
strings in the store currency. The harness converts them with exact decimal
arithmetic to the existing stored `budget_min`/`budget_max` integer fields. The
wire schema requests both new fields, while cached/legacy minor integers retain
their meaning and are never multiplied again. Whole JSON integers in the new
fields can be read too; floats, booleans, exponents, currency symbols, commas,
missing pairs, mixed units, fractional zero-decimal-currency amounts, reversed
ranges and amounts above the safe-integer limit fail validation. No rounding or
unit guessing is applied. `budget_max=0` retains its existing unspecified-limit
meaning. Cache entries remain canonical minor-unit personas.

The regression file initially has 37 failures and five passes, including the
legacy-minor checks. All 42 now pass through actual SDK parsing, wire-schema
checks, invalid boundaries and cache round trips. The diagnostic helper was
also replayed against saved real replies: it flags 12 issues in the initial
Japanese café run, eight in the profile-only prototype, and the exact duplicate
in the first rewritten-field prototype. Passing the later narrow checks still
does not establish varied customers: some final descriptions differ by only
one word, and the sampled demographics remain narrow. These limitations are
kept visible rather than reported as solved.

The first actual major-field run fixes the French amounts:
`persona-bookstore-json_schema-1792974419659736393`, three calls, 28.22 seconds,
raw `"5"`/`"20"` become stored 500/2000. Manual review also catches omitted
`preferred_categories`; the original numeric checks did not flag that omission.
The wire schema now requires that field while retaining the legacy empty-list
fallback. The fixture check now rejects empty preferences for these explicitly
buying customers. The 77 affected budget/preference/label regressions pass after
this final schema change.

Final French production rerun:
`persona-bookstore-json_schema-1792974619714728587`, three calls, 29.08 seconds,
passes both diagnostics. Each written customer retains 500–2000 cents and
`books`/`stationery`; the model sends plain euro amounts and conversion occurs
in code. Preferences and major fields are now requested together.

The Spanish USD trial before the required-preference adjustment,
`persona-us-json_schema-1792974457872268406`, completes three calls in 23.68
seconds but fails the budget check: the model explicitly writes `"0"`/`"0"`
despite the stated $3–$10 range, and omits preferences. Exact conversion cannot
recover a range the model did not supply. This semantic omission remains an
open issue; no values are inferred from unrelated numbers in the description.

Integration includes `73bbd13e`: mobile marketing lift charts and A/B arm cards,
full-width single-variant actions, a compact factorial-analysis entry, accurate
active-store tabs for unknown addresses, and designer option-name mentions.
Focused checks pass 214 unique backend cases and 30 frontend cases. Backend
strict typing reports zero errors/warnings and the server boots; TypeScript,
changed-file lint and the frontend production build pass (20.26 seconds).
One existing LiteLLM cleanup warning and the normal frontend chunk/plugin
warnings remain. No full suite was run.

Final Japanese production rerun: `persona-cafe-json_schema-1792974665733077558`, three calls, 25.22 seconds. Population checks: True; text diagnostics: True. Its saved cache was inspected for canonical minor-unit fields; no major-unit response fields are persisted.
