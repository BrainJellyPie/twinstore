# A purchase limit is not a selling price

On main `c481df2d`, the actual CPU VLM correctly transcribes **LIMIT 2 PER
CUSTOMER** and leaves its numeric price unknown. The capture converter
then interprets the quantity as an exact **$2.00** selling price. The
defect is in post-processing, rather than a fabricated model price.

The existing price-bound guard now recognizes `limit` / `limit of`,
`min` / `minimum` and `max` / `maximum`, including common abbreviated
punctuation and trailing minimum/maximum markers. These quantities or
bounds cannot establish an exact selling price. The literal tag and
product identity remain available; new items use a reviewable estimate,
and existing products retain their saved selling prices. Word boundaries
and the amount-adjacent checks preserve ordinary labels such as
`LIMITED OFFER $1.00`, `Limitless`, `Mini`, `Maxi` and `Maxwell`.

## Actual CPU observations

Qwen3.5-2B Q4_K_M, mmproj F16, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, reasoning disabled and temperature 0.
The synthetic bottle and shelf-edge fixture was visually inspected;
known geometry isolates label recognition and price conversion. This is
not a real-store photograph or a detector-accuracy benchmark. Every run
has two actual HTTP calls and zero application-cache hits. Times are
observations, not performance comparisons, because server prefix caching
varies.

The baseline native run takes 14.84 seconds and incorrectly stores 200
cents with `price_estimated=false`, despite the model's `price=null`.
All six final cases retain the printed qualifier and pass:

| Tag | Mode | Seconds | Stored result |
| --- | --- | ---: | --- |
| LIMIT 2 PER CUSTOMER | Native schema | 4.34 | 229 cents, estimated |
| MAX 2 PER PERSON | Native schema | 13.20 | 189 cents, estimated |
| MIN 2 PER ORDER | Native schema | 13.42 | 229 cents, estimated |
| LIMITED OFFER $1.00 | Native schema | 13.86 | 100 cents, exact |
| LIMIT 2 PER CUSTOMER | JSON | 17.61 | 189 cents, estimated |
| LIMITED OFFER $1.00 | JSON | 13.64 | 100 cents, exact |

The estimated amounts depend on the recognized product/category and still
need review; they are not claimed to be observed prices.

## Regression evidence

The first expanded price-limit and separate-tag tests report **60 failures
and 186 passes** on the parent. All **246** pass after the change. They
cover numeric model guesses, explicit currencies, full-width text, marker
punctuation, minimum/maximum suffixes, ordinary product names, existing
prices, separate image-tag requests in both wire modes and cached labels.

The focused suite passes **2,132 tests across 14 files in 5.18 seconds**,
with 45 existing LiteLLM asynchronous logging-cleanup warnings. Strict
Pyright has zero errors/warnings; application boot, probe compilation,
diff checks and byte-preservation of released changelog notes pass.
Frontend code is unchanged, inheriting 416's 55 UI tests and type/build/lint
checks. No full release suite is repeated; v0.8.2 remains unchanged.

Publication's main-branch lease detected a concurrent update to
`ddee3333525381606ebd1c0331f39980aeae5dff`. It integrates the other agent's
`025575f0` branch and changes only a stale expected parser-version string
in `test_ollama_qwen_direct_answers.py`. That update is merged and retained;
its additional **48 tests pass in 2.18 seconds**, with 17 existing cleanup
warnings. No application code changes in that concurrent update, so the
capture CPU results remain applicable. The publication is based on the
new main rather than overwriting it.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:
- Baseline: `capture-limit-baseline/capture-customer-limit-json_schema-1793053613866733165`.
- Final native limit: `capture-limit-final/capture-customer-limit-json_schema-1793053868847915402`.
- Final maximum: `capture-limit-final/capture-maximum-count-json_schema-1793053876048182315`.
- Final minimum: `capture-limit-final/capture-minimum-count-json_schema-1793053892097648306`.
- Native cash control: `capture-limit-final/capture-limited-price-json_schema-1793053908682992021`.
- JSON limit: `capture-limit-final/capture-customer-limit-json-1793053925629236412`.
- JSON cash control: `capture-limit-final/capture-limited-price-json-1793053946142240996`.

Logs: `/workspace/scratch/capture-limit-{baseline,before,core,tests,pyright,boot,final-cpu}.log`.
Focused list: `/workspace/scratch/capture-limit-test-files.json`.
Final result summary: `/workspace/scratch/capture-limit-final-summary.json`.
Concurrent-check log: `/workspace/scratch/capture-limit-concurrent-tests.log`.
