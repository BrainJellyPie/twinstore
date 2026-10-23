# Model failures masked by completed neighborhood visits

After the vision model answered once, later entrance failures could fall back to
rule-based plans and still produce successful customer visits. Neighborhood studies
used those visits for a completed vision-revenue report even when most model calls
failed. Requiring completed customer groups alone does not detect this case.

Each simulation condition now checks entrance-plan and shelf-glance failure counts
before continuing. As in marketing experiments, more than half the model calls
failing stops the study with an explanatory error. A failed first condition does
not trigger the second panel. Lesser failure rates remain usable with explicit
per-condition counts and fallback/skipped-glance warnings.

Verification:

- A scripted offline provider first answered successfully, then failed for the
  rest of the panel. Initial reproduction: 6 failed and 1 passed in 1.09 seconds.
- Final focused run: 54 passed in 4.87 seconds; Pyright passed.
- Real VLM engine and runner covered one or two initial successes followed by
  failures in either condition, exactly half failed calls and valid no-purchase
  decisions. No live provider was called.
- Eight additional metadata combinations cover glance-only failures, mixed
  planning/glance failures, zero calls, and the strict majority threshold.
- Existing visitor-group, opening-hour, scenario and currency cases stayed green.

The threshold follows the existing experiment policy. It does not prove that a
partially failed panel is unbiased, and the warnings remain part of its report.
