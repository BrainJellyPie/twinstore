# Respect country-qualified dollar prices in capture

On main `0ed937d1`, actual CPU label reads preserve `CA$1.00` and `HK$1.00`
but conversion accepts both as exact USD 1.00 in a USD store. `US$1.00`
already works as the matching control. The Canadian tag's synthetic image
was visually inspected; the six final labels preserve the exact printed
strings. These probes isolate VLM reading/conversion with known geometry,
not detector accuracy or real shelf photography.

The converter recognizes US$, CA$, AU$, NZ$, HK$, SG$ and NT$ as explicit
currency qualifiers, including case, spacing and full-width equivalents.
It maps them internally to the existing ISO currency checks without altering
the saved label. Foreign currencies remain estimated for review; no exchange
rate is invented. Bare $ retains the store's existing currency interpretation.
The normalized context also preserves savings, deposit, rate and price-limit
exclusions, and rejects negative amounts with combined code/symbol units.
These seven supported prefixes are not a universal currency-name classifier.

## Actual CPU checks

Qwen3.5-2B Q4_K_M with mmproj F16, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, disabled reasoning and temperature zero.
Every row makes two HTTP requests, one product read and one price-tag read,
with a fresh application cache and zero cache hits. Times are observations.

| Stage / printed tag | Wire mode | Seconds | Converted result |
| --- | --- | ---: | --- |
| Baseline CA$1.00 | Native schema | 14.24 | Incorrect exact USD 1.00 |
| Baseline HK$1.00 | Native schema | 14.77 | Incorrect exact USD 1.00 |
| Baseline US$1.00 | Native schema | 14.19 | Exact USD 1.00 |
| Repaired CA$1.00 | Native schema | 14.07 | Estimated USD 2.29 |
| Repaired HK$1.00 | Native schema | 13.91 | Estimated USD 2.29 |
| Repaired US$1.00 | Native schema | 13.67 | Exact USD 1.00 |
| Repaired CA$1.00 | JSON | 18.09 | Estimated USD 2.29 |
| Repaired HK$1.00 | JSON | 13.85 | Estimated USD 1.89 |
| Repaired US$1.00 | JSON | 14.12 | Exact USD 1.00 |

All six final checks pass. The estimated amounts come from the existing
catalog fallback, not observation or currency conversion. Product identity
and original price text are retained.

## Regression verification and integration

The new file fails 165 cases and passes 40 on the parent, then passes all
205. It covers every distinct pair among the seven currencies, numeric model
guesses, matching literal/free prices, savings/deposit/rate/limit/negative
contexts, full-width text, conflicting ISO qualifiers and word boundaries.
Six additional existing HTTP/cache cases exercise foreign qualified amounts
through capture conversion in both wire modes; the extended currency file
and new suite together pass 314 cases.

All 2,057 tests across 14 affected/adjacent capture files pass in 5.08
seconds with 45 existing LiteLLM asynchronous logging-cleanup warnings.
Strict Pyright reports zero errors/warnings. Boot, probe compilation and
diff checks pass. No full suite is rerun.

The external branch's `08372585` only merges already integrated main
`0ce64416` into `14bd0504`. Preserve its ancestry and retain the complete
current changelog when resolving paragraph-order conflicts. No additional
external application change is introduced. Frontend code is unchanged and
inherits 412's 83 UI tests and TypeScript/lint/build; structured parsing is
unchanged and inherits 413's 1,225 focused checks. Released notes and v0.8.2
remain unchanged.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:
`capture-qualified-baseline/` and `capture-qualified-final/` contain the
images, request/reply bodies and results. The first baseline is
`capture-foreign-cad-price-json_schema-1793050506061527243`; the last final
case is `capture-qualified-price-json-1793050827862659298`.
Logs: `/workspace/scratch/capture-qualified-{baseline,before,core-tests,final-cpu,tests,pyright,boot}.log`.
Focused file list: `/workspace/scratch/capture-qualified-test-files.json`.
