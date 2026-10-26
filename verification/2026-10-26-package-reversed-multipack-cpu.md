# Preserve reversed multipack quantities during package linking

An actual CPU Qwen3.5-2B Q4_K_M run reads `500 ml x 6` correctly, including
the complete size field, but links it to the catalog's single 500 ml product.
The evidence filter only recognized multiplication with counts before the
unit quantity. Its parent run takes **19.98 seconds and two HTTP requests**.

Package evidence now recognizes counts before and after the quantity, including
`2 x 500 ml x 3`. Multiplication signs after unit text are retained and
normalized. A complete expression is kept together during token comparison;
otherwise its trailing count can incorrectly bind to a catalog's trailing
brand name as if the brand were a measurement unit. Both filtering and token
evidence require the complete expression, so partial packs are not substitutes.
Matching still depends on observed words and the separate matching call. No
missing quantities or mathematically equivalent but unprinted pack names are
invented, and prompts are unchanged.

## Focused regression checks

The first label-order regression has **12 failures and 64 passes** on the
parent. An intermediate correction exposes the trailing-brand token boundary;
the final atomic-expression correction preserves that valid link too.
Wire/cache cases exercise both JSON modes, wrong matcher output, Unicode and
asterisk multiplication, a changed catalog reusing the same image observation,
and nested pack expressions.

A new wire fixture initially printed both a nested pack and a different
multipack reference while expecting a match. The existing conservative rule
requires all observed pack expressions, so those four fixture expectations
were invalid. The wire case now uses a single-unit reference, and an explicit
negative test retains conservative handling of two differing expressions.

The final ten package engine/API files pass **338 tests in 9.75 seconds**,
with 46 existing dependency/resource warnings. Strict Pyright reports zero
errors or warnings; application import, probe compilation and diff checks pass.
Frontend code is unchanged and inherits integration 422's 207 focused tests,
successful build/typecheck and clean changed-file lint.

## Actual CPU checks

The fixture is a deterministic synthetic package drawing, visually inspected,
not a real product photograph. The runtime is llama.cpp b11878, five CPU
threads, no GPU, context 8192, temperature 0, reasoning off, image limit 512.
Every run has a fresh application cache and uses actual model inference.

The initial native-schema request, response and image in the final single-unit
rejection case are exactly equal to the parent run. The final application
filters out the wrong catalog candidate after observation and needs only one
HTTP request, rather than accepting the same observation and then linking the
single unit. This comparison is saved in `pack-reversed-reproduction.json`.

All **six fresh final cases pass** their product-link checks, with zero
application cache hits:

| Case | Native schema | JSON |
| --- | --- | --- |
| Reversed pack, only the wrong single-unit catalog entry | 3.33 s / 1 HTTP / unlinked | 18.49 s / 1 HTTP / unlinked |
| Reversed pack, correct catalog entry also available | 4.76 s / 2 HTTP / correct pack | 6.40 s / 2 HTTP / correct pack |
| Existing count-first pack control | 17.07 s / 2 HTTP / correct pack | 18.03 s / 2 HTTP / correct pack |

The native responses leave the dedicated brand field empty even though the
name/printed observation contains Leafy. These checks establish the linking
fix, not perfect metadata or general OCR quality. Different printed pack
expressions remain conservatively unlinked; arithmetic substitution of
unprinted counts is not introduced. Full result paths and outputs are in
`/workspace/scratch/pack-reversed-final-summary.json`.

Artifacts: `/workspace/scratch/pack-reversed-baseline/`,
`/workspace/scratch/pack-reversed-final/`, and the test/check logs and summaries
under `/workspace/scratch/pack-reversed-*`. Reproduce with
`verification/local-model-probe.py --case pack-multipack-reversed-unlisted`
or `--case pack-multipack-reversed`, selecting either JSON mode and the
loopback endpoint.
