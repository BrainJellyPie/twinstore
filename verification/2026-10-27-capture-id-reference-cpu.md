# Do not turn captured product IDs into selling prices

The CPU VLM accurately reads `ID 1234` from a synthetic bottle/tag image,
but capture previously stores it as an exact 1,234-cent USD price. The tag
contains a product identifier, not a selling price. Add `ID` to the existing
nonmonetary reference-prefix guard, alongside SKU, ITEM and REF. The raw
transcription and product identity are preserved. Existing catalog prices
remain unchanged when applying the capture; a new product's catalog estimate
stays explicitly marked for review.

The expanded reference tests initially reproduce **20 failures and 199
passes**. Final checks across four relevant price/capture files pass **720
tests in 3.40 seconds**, with 21 existing LiteLLM coroutine warnings. Cases
include numeric model guesses, unspaced IDs, punctuation, full-width digits,
zero, currency-marked prices and words such as VALID, SOLID and IDEAL. An
IDR currency code remains a currency code. Strict Pyright reports zero errors
and warnings; application import, probe compilation and diff checks pass.
Frontend code is unchanged and inherits integration 434's checks.

## Fresh CPU evidence

Qwen3.5-2B Q4_K_M runs through llama.cpp b11878 with five CPU threads, no GPU,
context 8192, reasoning disabled, image limit 512 and temperature zero. Three
completed runs each use two real HTTP requests and zero application cache
hits. The fixture was visually inspected and uses known crops; it is not a
real shelf photograph or a detector benchmark. One earlier probe attempt
had a missing fixture-map entry and made no HTTP requests; it is excluded.

| Revision / output mode | Seconds | Stored price | Estimated |
| --- | ---: | ---: | --- |
| Before / native schema | 14.44 | 1,234 cents (incorrect) | no |
| After / native schema | 3.81 | 229 cents | yes |
| After / JSON | 17.49 | 189 cents | yes |

Every price reply contains `ID 1234`. Both native request bodies, both reply
messages and all three input images exactly match before and after. The
parser fix prevents the incorrect exact price. The native server may reuse
an input prefix; these timings do not establish faster inference. Estimated
values depend on the recognized product and still require review. The model
leaves the brand empty, so the result is not a general metadata-quality claim.

Reproduce with `capture-id-code` in `verification/local-model-probe.py`.
Artifacts are under `/workspace/scratch/capture-id-baseline/` and
`capture-id-final/`. Values and timings are in `capture-id-summary.json`;
request, reply and image comparisons are in `capture-id-reproduction.json`.
Test and check logs use the `capture-id-` prefix. The v0.8.2 release files
are unchanged; this correction is an Unreleased change.
