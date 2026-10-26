# Keep nutrition quantities out of captured selling prices

Actual CPU reads on main `ec878593` transcribed `100 kcal`, `CALORIES 100`
and `ENERGY 100 kJ` correctly, but conversion turned each number into an
exact 1.00 USD selling price. The three semantic probes failed. Their
synthetic images were visually inspected for legible, unclipped labels;
this isolates real VLM reading and conversion, not shelf detection accuracy.

The converter now recognizes calorie/energy units and marked nutrition
quantities without monetary units. Printed nutrition text remains visible,
new products retain an estimated catalog fallback, and applying the capture
to a matched existing product keeps its saved selling price. A model's
numeric price guess cannot override the nonmonetary label. Currency-bearing
prices, ordinary bare numeric price tags and product names remain usable.
Recognition is limited to the supported unit/prefix vocabulary; this is not
a general semantic classifier for every label.

## Actual CPU checks

Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, disabled reasoning and temperature zero. Each row
uses two actual HTTP requests (product reading and separate tag
transcription), a fresh application cache and zero application cache hits.

| Stage / tag | Mode | Seconds | Outcome |
| --- | --- | ---: | --- |
| Baseline 100 kcal | Native schema | 13.55 | Incorrect exact 1.00 USD |
| Baseline CALORIES 100 | Native schema | 15.08 | Incorrect exact 1.00 USD |
| Baseline ENERGY 100 kJ | Native schema | 14.18 | Incorrect exact 1.00 USD |
| Repaired 100 kcal | Native schema | 12.89 | Estimated 1.89 USD |
| Repaired CALORIES 100 | Native schema | 13.45 | Estimated 2.29 USD |
| Repaired ENERGY 100 kJ | Native schema | 13.34 | Estimated 2.29 USD |
| Repaired 100 kcal | JSON | 17.59 | Estimated 1.89 USD |
| Repaired CALORIES 100 | JSON | 13.10 | Estimated 1.89 USD |
| Exact $1.00 control | Native schema | 13.57 | Exact 1.00 USD retained |

All six final cases pass. Estimated fallback amounts are not claims about
an observed selling price. Product identity and printed tag text are
preserved. Times are observations, not benchmarks.

## Regression checks and evidence

The new tests fail 81 cases and pass 12 on the parent, then pass all 93
after the repair. They cover English/Korean/Japanese/Chinese/Spanish unit
labels, full-width text, prefix/suffix forms, model price guesses, explicit
cash/cents controls and placement with known/new products. Broader
verification passes 1,837 cases across 13 affected/adjacent capture files
in 4.65 seconds, with 39 existing LiteLLM asynchronous-logging cleanup
warnings. Strict Pyright reports zero errors/warnings; boot, probe
compilation and diff checks pass. No full suite is rerun.

Frontend and online application/domain code are unchanged, inheriting the
preceding 88 UI and 33 online API checks plus TypeScript/lint/build.
Released changelog text and v0.8.2 tag/assets remain unchanged.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:
- `capture-nutrition-baseline/` contains the three failed real-model results.
- `capture-nutrition-final/` contains the six passing real-model results,
  beginning with `capture-calorie-quantity-json_schema-1793047863912790487`.

Logs: `/workspace/scratch/capture-nutrition-{baseline,before,core-tests,final-cpu,tests,pyright,boot}.log`.
Focused file list: `/workspace/scratch/capture-nutrition-test-files.json`.
