# Preserve Vietnamese dong units on captured tags

A synthetic bottle image has a clearly printed `₫1000` tag. The CPU VLM
transcribes it as `d1000`. Previously the capture accepts this as an exact
1,000-cent USD price ($10.00). For a VND store the same transcription already
retains the correct 1,000-dong amount.

Recognize `₫` in the currency map and canonicalize isolated `d` or `đ`
immediately before or after a number for price parsing. The original tag
text stays unchanged. An embedded letter inside `USD`, `CAD` or a word is
not a dong unit. Existing savings, negative-price, deposit, bounds and
unit-rate guards still apply. A foreign amount cannot override the store
currency, including when the model supplies a numeric guess. The fallback
is a catalog estimate marked for review, not an exchange-rate conversion.
Applying a capture preserves an existing product's price.

## Actual CPU runs

Qwen3.5-2B Q4_K_M runs through llama.cpp b11878 with five CPU threads, no GPU,
context 8192, reasoning off, image limit 512 and temperature 0. These six
fresh runs use two HTTP requests each and zero application cache hits.
Replies are neither mocked nor replayed. The visually inspected synthetic
image uses DejaVuSans-Bold for the dong glyph and known tag crops; this is
not a real photograph or a detector benchmark.

| Code / currency / output mode | Seconds | Stored price | Estimated |
| --- | ---: | ---: | --- |
| Before / USD / native schema | 14.76 | 1,000 cents (incorrect) | no |
| Before / VND / native schema | 11.65 | 1,000 dong | no |
| After / USD / native schema | 11.48 | 229 cents | yes |
| After / VND / native schema | 11.52 | 1,000 dong | no |
| After / USD / JSON | 17.76 | 229 cents | yes |
| After / VND / JSON | 11.28 | 1,000 dong | no |

All six price replies contain `d1000`. For each native before/after pair,
both request bodies, both reply messages and all three image files are
identical. Response envelopes differ in request metadata. The parser
change prevents the incorrect exact USD price. A symbol-only change would
not address the observed ASCII transcription. The model still leaves the
brand empty, so passing these checks does not establish general metadata
or price-recognition accuracy.

## Regression checks

Before the change the expanded currency tests have 182 failures and 111
passes. The first two-file check after the change passes 556 tests. Further
foreign-zero cases bring the final fifteen-file price and capture suite to
**2,615 passing tests in 5.81 seconds**, with 45 existing LiteLLM coroutine
warnings. Coverage includes matching and conflicting currencies, numeric
model guesses, Unicode digits, zero, negative and non-selling amounts,
literal unit preservation, product identity and existing-price preservation.
Strict Pyright, application import, probe compilation and diff checks pass.
Frontend code is unchanged and inherits integration 434's verified checks.

Artifacts are under `/workspace/scratch/capture-dong-baseline/` and
`capture-dong-final/`. Full paths, values and timings are recorded in
`capture-dong-summary.json`; request, reply and image comparisons are in
`capture-dong-reproduction.json`. Test and check logs share the
`capture-dong-` prefix. Reproduce with `capture-foreign-vnd-price` and
`capture-vnd-price` in `verification/local-model-probe.py`.
