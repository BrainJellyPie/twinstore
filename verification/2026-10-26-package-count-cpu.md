# A multipack must not link to a single-unit catalog item

This follow-up remains outside v0.8.2. Actual Qwen3.5-2B Q4_K_M CPU calls
reproduced wrong links for two label styles. The observation correctly
transcribed `LEAFY GREEN TEA 6 x 500 ml`, then the text matching call chose
`Leafy Green Tea 500 ml`. A separate `500 ml / 6 PACK` fixture did the same,
even though `printed_text` retained `6 PACK`. Its separate `size` field
contained only `500 ml`, so the guard must use the complete printed evidence.

The two directly inspected 600×800 synthetic bottle-shaped label fixtures
test printed identity, not whether an image visually depicts six physical
bottles. They are not shop photographs. llama.cpp b11878 used five CPU
threads, no GPU and an 8,192-token context. Catalog candidates are still
excluded from the visual observation prompt.

Candidate filtering now requires the observed multiplication expressions and
recognized pack counts to occur in supported catalog names. It normalizes
`×`, `*`, uppercase/full-width `X` and spacing between numbers. Recognized
count forms include `6 pack`, `6-pack`, `6 pk`, `pack of 6` and selected
Korean/Japanese count suffixes. Counts are recognized before splitting letters
from digits, so `B6 PACK` is not treated as six packs. Existing word, variant,
quantity/unit, duplicate-name and large-catalog checks remain in force.

This is bounded evidence matching, not a universal unit/count translator.
Equivalent but differently worded catalog descriptions can still need manual
review, and a count omitted by visual transcription cannot be recovered here.

Actual JSON Schema calls, each with a fresh application cache and no cache hits:

| Label | Catalog | Result | HTTP calls | Time |
| --- | --- | --- | ---: | ---: |
| `6 x 500 ml`, before | Single only | Wrong single-unit link | 2 | 18.27 s |
| `6 x 500 ml`, after | Single only | No unsupported link | 1 | 3.46 s |
| `6 x 500 ml`, after | Single + correct multipack | Correct multipack link | 2 | 4.67 s |
| `500 ml / 6 PACK`, before | Single only | Wrong single-unit link | 2 | 17.65 s |
| `500 ml / 6 PACK`, after | Single only | No unsupported link | 1 | 3.32 s |
| `500 ml / 6 PACK`, after | Single + correct multipack | Correct multipack link | 2 | 4.78 s |

Server prompt-prefix reuse affects timing; this is not a speed benchmark.
Rejected candidates avoid the second matching call, while product observation
is retained. No perfect brand/size extraction is claimed.

A separate plain-JSON run of the `6 PACK` / single-only case also passed:
one actual HTTP request, zero cache hits, 18.75 s. The captured wire mode
was `json_object`; the observed pack was retained without a single-unit link.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `pack-count-before/pack-multipack-unlisted-json_schema-1793010601009064242`
- `pack-count-after/pack-multipack-unlisted-json_schema-1793010926884597108`
- `pack-count-match/pack-multipack-json_schema-1793010979572913602`
- `pack-count-word-before/pack-multipack-count-unlisted-json_schema-1793011128630482444`
- `pack-count-word-after/pack-multipack-count-unlisted-json_schema-1793011401964589251`
- `pack-count-word-match/pack-multipack-count-json_schema-1793011408152867349`
- `pack-count-word-json/pack-multipack-count-unlisted-json-1793012270712035074`

The initial multiplication regressions produced five failures and 21 passes.
The added word-count cases then produced six failures and 32 passes before
their guard was added. All 152 package tests finally passed in 4.29 s, with
14 existing LiteLLM logging cleanup warnings. Coverage includes nested packs,
wrong counts/units, reordered labels, repeated printed counts, full-width text,
recognized count suffixes and non-count text controls.
Strict backend Pyright reported zero errors/warnings. The app import, probe
compilation and diff checks passed. Frontend code is unchanged.
