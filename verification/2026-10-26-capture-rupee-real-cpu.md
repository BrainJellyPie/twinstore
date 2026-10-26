# Preserve rupee and Brazilian real price units

The CPU VLM correctly transcribes `₹100` and `R$1.00`, but the previous
conversion accepts both as an exact 100-cent USD price. For an INR store it
also converts `₹100` to 100 minor units (one rupee), instead of 10,000 minor
units. The native-schema baselines take 13.69, 13.74 and 11.51 seconds,
respectively, with two real HTTP requests each.

Recognize `₹` as an INR major-unit mark and `R$` as BRL. Derive symbol checks
and context stripping from the same currency map so these signs retain
their unit meaning and existing savings, bounds, deposit and unit-rate
guards. A foreign amount cannot override the store currency, even when the
model supplies a numeric guess. Bare shared dollar signs and embedded word
endings such as `BAR$1.00` retain their previous handling. No exchange-rate
conversion or prompt change is introduced. Estimated fallback prices stay
marked for review; applying a capture preserves an existing product price.

Before the change the three expanded files have **106 failures and 297
passes**. Afterward all **403 pass in 3.63 seconds**. The final fifteen price
and capture files pass **2,361 tests in 5.62 seconds**, with 45 existing
dependency/resource warnings. They cover foreign and matching currencies,
conflicting ISO codes, Unicode digits, zero/negative amounts, western and
Indian grouping, non-selling tags, product identity and existing-price
preservation, both HTTP output modes and cache reuse. Strict Pyright reports
zero errors or warnings; application import, probe compilation and diff
checks pass. Frontend code is unchanged and inherits integration 426's checks.

## Fresh CPU evidence

These are visually inspected synthetic bottle/tag images with known tag
crops, not real shelf photographs or a detector benchmark. Qwen3.5-2B
Q4_K_M runs with llama.cpp b11878, five CPU threads, no GPU, context 8192,
reasoning off, image limit 512 and temperature 0. All six final runs use
fresh caches, two HTTP requests and zero application cache hits; none replay
or mock replies.

| Tag / store currency / output mode | Seconds | Result in minor units |
| --- | ---: | --- |
| ₹100 / USD / native schema | 11.86 | estimated 229 |
| ₹100 / INR / native schema | 11.50 | exact 10,000 |
| R$1.00 / USD / native schema | 13.99 | estimated 229 |
| R$1.00 / BRL / native schema | 11.68 | exact 100 |
| ₹100 / USD / JSON | 17.19 | estimated 189 |
| ₹100 / INR / JSON | 11.59 | exact 10,000 |

For each of the three baseline cases, both final native requests, both
model replies and the image exactly equal the baseline. The conversion
change prevents the incorrect exact price. Estimated values depend on the
recognized catalog identity and still require review. The model leaves the
brand field empty; passing these price checks is not a metadata-quality claim.

## Fixture correction and artifacts

The first two exploratory INR images used NotoSansCJK-Bold.ttc, which drew
the rupee sign as a missing-glyph box. The model returned `☐100`. Those two
runs are a fixture defect, not evidence of rupee recognition, and are not
included in the baselines above. The probe now uses DejaVuSans-Bold.ttf for
rupee tags and records the font path. These cases require that font; other
fixtures retain their existing font. Corrected images visibly contain `₹`.

Artifacts are under `/workspace/scratch/capture-more-currency-baseline/`,
`capture-more-currency-baseline-glyph/` and `capture-more-currency-final/`.
The corrected INR baselines end in `1793058267302872440` and
`1793058283989378238`; the BRL baseline ends in `1793058133281412572`.
Full final paths, values and timings are in `capture-more-currency-final-summary.json`;
input/reply comparisons are in `capture-more-currency-reproduction.json`.
Test/check logs and command timings share the same prefix. Reproduce using
`capture-foreign-inr-price`, `capture-inr-price`, `capture-foreign-brl-price`
and `capture-brl-price` in `verification/local-model-probe.py`.
