# Keep short item/reference labels out of captured selling prices

The CPU model correctly reads `ITEM #1234` and returns no numeric price, but
the previous conversion turns its identifier into an exact USD price of
1234 cents. The actual baseline takes **14.84 seconds and two HTTP requests**.
This is an application interpretation error after a usable transcription.

The existing reference-number guard now also recognizes bare item, article,
product, reference/ref labels and hash-prefixed numbers. The existing suffixes
`no.`, `number` and `code`, punctuation and Unicode normalization still work.
The guard remains limited to tags without explicit currency evidence, so
`ITEM $1.00` stays an exact one-dollar price. Ordinary price text and words
such as Itemized, Productivity and Refill are preserved. No prompts change.
Printed labels remain available for review, estimated prices stay marked as
estimates, and applying a capture preserves the price of an existing product.

Before the change the expanded reference-code file has **57 failures and
125 passes**. Afterward, the reference-code and separate-tag checks pass
**233 tests in 3.10 seconds**. The final fourteen price/capture files pass
**2,214 tests in 5.07 seconds**, with 45 existing dependency/resource warnings.
They include model price guesses, whole/decimal currencies, Unicode labels,
word boundaries, real cash controls, existing-product preservation and both
HTTP output modes with cached observations. Strict Pyright has zero errors or
warnings; application import, probe compilation and diff checks pass.
Frontend code is unchanged and inherits integration 424's checks.

## Fresh CPU evidence

The visually inspected image is a deterministic synthetic cola package and
tag. Known geometry supplies the tag crop; this is not a real photograph or
detector benchmark. Qwen3.5-2B Q4_K_M runs through llama.cpp b11878 with five
CPU threads, no GPU, context 8192, reasoning off, image limit 512 and
temperature 0. No replies are mocked/replayed; all runs use fresh caches.

All **six final cases pass**, each using two actual HTTP requests and zero
application cache hits:

| Tag and output mode | Seconds | Result |
| --- | ---: | --- |
| ITEM #1234, native schema | 3.95 | estimated 229 cents |
| REF 1234, native schema | 13.54 | estimated 229 cents |
| #1234, native schema | 13.49 | estimated 189 cents |
| ITEM $1.00, native schema | 13.98 | exact 100 cents |
| ITEM #1234, JSON | 17.74 | estimated 189 cents |
| ITEM $1.00, JSON | 13.58 | exact 100 cents |

Both request bodies, both model replies and the fixture image in the final
native ITEM case exactly equal the baseline. The changed conversion, rather
than a different model answer, prevents the false exact price. Estimated
values depend on the recognized catalog identity and still require review;
they are not assertions about the printed selling price. Missing identifier
text in an OCR reply remains an observation limitation.

Artifacts are under `/workspace/scratch/capture-reference-alias-baseline/`
and `capture-reference-alias-final/`. The baseline case is
`capture-item-code-json_schema-1793057387705268864`. Full final paths, values
and timings are in `capture-reference-alias-final-summary.json`; exact input/
reply comparisons are in `capture-reference-alias-reproduction.json`.
Test/check logs and command timings use the same prefix. Reproduce using
the `capture-item-code`, `capture-reference-code`, `capture-hash-code` and
`capture-item-price` cases in `verification/local-model-probe.py`.
