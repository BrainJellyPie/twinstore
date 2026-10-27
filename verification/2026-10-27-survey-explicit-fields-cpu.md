# Concept drafts: explicit images, prices and customer quotas

On main `46bf19938249f0027f3b092e0ad4e01361c03dc7`, actual 0.8B and 2B
models omitted the image list while describing both requested packs in prose.
The application therefore returned no selected images and removed the
two-image preference question. Explicit free/USD prices and customer quotas
were also omitted or replaced by null/empty lists even when the prose repeated
them. All six initial baseline cases failed the field-level expectations.

## Change

The concept-draft wire schema now requires explicit images, price, quotas and
text fields, and omits defaults that suggest they can be skipped. Structured
selections precede the explanatory name/context/rationale. Existing runtime
defaults remain: older partial drafts and cached records still validate.

The prompt distinguishes the available question list from the questions the
manager actually requested, puts named customer groups into quota fields, and
makes an explicitly stated price take precedence over missing or ambiguous
catalog offers. Zero remains a free offer; null remains an unknown price.
No price is clamped, guessed or copied from a different image by application
code. Internal/public field names and conversion rules are unchanged.

## Actual CPU results

Qwen3.5-0.8B and Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads,
no GPU, context 8192, reasoning disabled. The probe uses the production concept
draft's temperature 0.2 and 1200-token output budget, seed 0 and normal two
validation attempts. Every run has a fresh application cache; server prompt
prefix reuse is possible. This is text drafting from an image-library fixture,
not image recognition or a respondent survey.

Final source SHA-256:
`6aa36202086236be4b41de0687b1c3dd56dc56ea17cec05042e49ac684a4022e`.

| Model | Case | Mode | Seconds | Result |
| --- | --- | --- | ---: | --- |
| 0.8B | Explicit free offer | Native schema | 6.40 | Pass: price 0, both images, requested questions and 20s/Female quotas |
| 0.8B | Explicit $2.50 | Native schema | 6.35 | Pass |
| 0.8B | Unknown price | Native schema | 5.46 | Pass: null retained |
| 0.8B | No demographic restriction | Native schema | 5.10 | Pass: empty quotas retained |
| 0.8B | Korean 2,500-won request | Native schema | 9.32 | Images, price and quotas correct; **requested question set still wrong** |
| 0.8B | Men in their thirties | Native schema | 6.29 | Images, price, questions and gender correct; **age is wrongly 20s** |
| 2B | Explicit free offer | Native schema | 12.99 | Pass |
| 2B | Korean 2,500-won request | Native schema | 12.68 | Pass |
| 2B | Explicit $2.50 | Native schema | 11.93 | Pass |
| 2B | Unknown price | Native schema | 10.84 | Pass |
| 2B | Men in their thirties | Native schema | 11.97 | Pass |
| 2B | Two ambiguous shelf prices | Native schema | 9.76 | Pass: neither offer selected as the price |
| 2B | Explicit price overriding two shelf offers | Native schema | 9.52 | Pass: requested $2.50 retained |
| 2B | Explicit free offer | JSON | 17.98 | Pass |
| 2B | Korean 2,500-won request | JSON | 18.30 | Pass |

The final source has **15 actual runs, 15 HTTP calls: 13 full field-level
passes and 2 explicit semantic failures**. It does not make every tiny-model
interpretation reliable. The older main also failed the 0.8B men-in-thirties
control, omitting both quotas as well as images/price. Final prose can still
invent context, such as suggesting both packs share image A's price; the probe
does not establish arbitrary prose fidelity. Drafts remain reviewable before
running a study.

## Withheld experiments

Across all baselines/candidates/controls, **41 runs and 41 HTTP calls** completed
with zero application cache hits. Intermediate required-field/order changes
restored images but did not fix price or quota interpretation. A shorter `price`
wire alias did not help and was removed. A full age-mapping list made the small
model choose the first age label and regressed the free price; it was also
removed. The restored final source exactly matches the hash of the successful
price-priority controls. A folder called `survey-explicit-final-2b` contains an
earlier failed candidate, not the published result.

## Regression coverage and evidence

New wire-contract tests reproduced six failures against the parent (5 other
checks passed, 1.11 seconds). They cover omitted selections versus explicit
unknowns, zero/positive/null prices, image order, canonical cache round trips,
and older partial drafts. Existing survey suites also cover missing/ambiguous
images, different shelf offers, conversion bounds, currency rounding, optional
nulls and real SDK request/cache boundaries.

Final verification: **456 tests across 14 survey engine/API files passed in
10.78 seconds** (88 existing LiteLLM logging-cleanup warnings). Strict Pyright
reported zero errors/warnings; the server application import and probe
compilation passed. Frontend validation is inherited from unchanged main 463.

`verification/local-survey-probe.py` retains all eight diagnostic scenarios.
It checks image identities/order, exact price/currency, question set, age/gender
quotas, warnings and source-catalog immutability. Its nonzero status for the
two smaller-model failures is deliberate. The source path/hash, requests,
responses and final draft are saved for each actual run.

`/workspace/scratch/survey-explicit-run-index.json` lists all 41 results.
Final-source results are in `survey-price-priority-candidate`,
`survey-price-priority-controls`, and `survey-price-priority-offer-controls`
under `/workspace/scratch`. Earlier candidates and the original baselines are
also indexed; no failed run is counted as successful.

Frontend code and the published v0.8.2 tag/assets are unchanged.
