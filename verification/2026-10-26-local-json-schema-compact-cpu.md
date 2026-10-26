# Compact bulky schemas in local JSON prompts

On main `3cdecf24`, the plain-JSON design request to make delivery free and
remove the welcome popup applied only the popup change. The final baseline
from the previous delivery-threshold investigation used 3,962 prompt tokens
and left the 499-cent fee untouched. A prior frozen-parent version instead
copied the schema until both 900-token responses were truncated. The schema
itself occupied 12,946 characters in Instructor's indented representation.

For loopback endpoints in plain JSON mode, schemas of at least 4,096
characters are now serialized without indentation before the SDK sends the
request. The same complete schema occupies 5,547 characters for design chat;
no property, constraint, description or enum is removed. An existing SDK
request hook replaces only the exact schema text inside system messages.
User text, images, native JSON-schema requests and non-loopback requests
retain their existing format. Repeated validation attempts remain bounded.
Changed prompts have a distinct cache identity; small schemas retain their
previous cache identity and request text.

The combined design request now uses 2,131 prompt tokens and changes both
the fee to zero and the popup to none, preserving every other option. This
is a result for the tested CPU model, not a guarantee that all local models
will obey combined requests. It is not a latency benchmark: the server may
reuse prompt prefixes even when the application's response cache is fresh.

## A regression caught before publication

The initial implementation compacted small schemas too. In a customer
description for a bookstore open only Tuesday and Thursday, that candidate
added weekend visits. The original main request retained the stated days.
The broad change was withheld. Applying the final large-schema-only policy
restored the original small request byte-for-byte and produced the same
description as the main control. Manual review confirmed the supplied days,
18:00–21:00 hours, used books/stationery, and $5–20 budget. Demographic
estimates in the prose are not validated population data. The probe leaves
these free-text cases at `success: null` for human review; a syntactically
valid response was not counted as semantic success.

An earlier development invocation also stopped before any HTTP request
because a refactor had left one reference to a removed `loopback` local.
That local was restored using the extracted helper before verification.
Neither the incomplete refactor nor the broad prompt change was published.

## CPU checks

Qwen3.5-2B Q4_K_M with its F16 vision projector, llama.cpp b11878, CPU only,
five threads, 8,192-token context, reasoning disabled. All listed model runs
used fresh application caches and reported zero cache hits. Generation
budgets and retry counts were not raised.

| Request | Mode | HTTP calls | Time | Observed result |
| --- | --- | ---: | ---: | --- |
| Free delivery and remove popup | JSON | 1 | 15.61 s | Both changes, no unrelated changes |
| Free-delivery threshold zero | JSON | 1 | 5.77 s | Threshold zero, stored fee retained |
| Threshold $7.25 | JSON | 1 | 5.76 s | Threshold 725 cents, stored fee retained |
| Korean color-only request | JSON | 1 | 16.69 s | Only theme color changes |
| Free delivery and remove popup | Native schema | 1 | 8.98 s | Both changes; native format unchanged |
| `DEPOSIT INCLUDED $1.00` image | JSON | 2 | 17.72 s | Exact selling price 100 cents |
| Bookstore customer description | JSON | 1 | 5.01 s | Manual supplied-constraint review passes |
| Compact convenience-store automatic products | JSON | 2 | 64.19 s | All 12 racks assigned; 10 SKUs, 92 placements |

Zero, fractional, color and native controls were run before the final size
gate was added; their schema sizes/modes yield the identical wire policy in
the final implementation. The combined request, image and customer draft
were rerun after that restriction. The price image is a synthetic fixture,
not a real-store photograph or a detector accuracy benchmark.
The starter case also ran the production placement path with no missing or
unknown rack IDs. This does not close the separate persona-budget adherence
and unsupported never-free-shipping findings from earlier investigations.

## Automated checks

The new transport regressions use actual SDK adapters and intercepted HTTP:
synchronous/asynchronous text and images, invalid-answer correction, cache
replay, original user content and image preservation, Unicode descriptions,
localhost/IPv6, remote JSON and native-schema controls. Eight fail against
the frozen parent; all 19 pass after the change. The original small prompt
and cache compatibility are explicitly checked.

The focused suite passes 410 tests across 17 files in 9.36 seconds. Its 82
warnings are the existing LiteLLM asynchronous logging cleanup warnings.
Strict Pyright reports zero errors/warnings; application boot and diff
checks pass. Frontend code is unchanged. The full release suite was not
repeated for this client change. v0.8.2 and its release notes are unchanged.

Logs: `/workspace/scratch/compact-schema-{focused-tests,pyright,boot}.log`,
`compact-schema-tests-parent.log`, and
`compact-schema-profile-semantic-review.json`.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Prior failing combined request: `design-delivery-verified-design-free-popup-json/design-free-popup-json-1793029434547461988`.
- Final combined: `json-schema-compact-final-design-free-popup/design-free-popup-json-1793031637049777675`.
- Threshold zero: `json-schema-compact-design-always-free-json/design-always-free-json-1793031332669612695`.
- Fractional threshold: `json-schema-compact-design-threshold-fractional-json/design-threshold-fractional-json-1793031341370488028`.
- Korean color: `json-schema-compact-design-color-ko-json/design-color-ko-json-1793031349848992627`.
- Native combined: `json-schema-compact-design-free-popup-json_schema/design-free-popup-json_schema-1793031398903471238`.
- Final image: `json-schema-compact-final-capture-deposit-included-price/capture-deposit-included-price-json-1793031663785086249`.
- Withheld small-schema regression: `json-schema-compact-profile-draft-bookstore-json/profile-draft-bookstore-json-1793031388828663180`.
- Original small-schema control: `json-schema-original-profile-draft-bookstore/profile-draft-bookstore-json-1793031440221943185`.
- Final small-schema control: `json-schema-compact-final-profile-draft-bookstore/profile-draft-bookstore-json-1793031655660776082`.
- Final automatic products: `json-schema-compact-final-compact/compact-json-1793031684577245998`.
