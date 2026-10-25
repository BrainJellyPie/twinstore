# Give survey commentary the conditions respondents saw

The survey reading used only the aggregate report, which does not contain
the respondent brief or reference price from its saved request. An analyst
therefore received ratings without the product framing or displayed price.

Reading material now includes those saved conditions as notes on an in-memory
report copy. Product A's price uses the request currency and includes zero.
Missing conditions and reports without a request do not gain inferred values.
Existing report, request and status files are not modified.

Twenty pre-fix failures reproduced missing conditions. Twenty-four HTTP
cases cover JSON/JSON Schema, USD/KRW, blank or bilingual briefs and missing,
zero or positive prices; a legacy-request-absence control is also included.
The real application write/read path and LiteLLM/Instructor verify model
input, unchanged aggregates and source files, persisted commentary, and
cache reuse on identical repeats.

Focused condition, bounded-report, required-summary and reading API suites:
59 passed in 4.13 seconds. Full-source Pyright: zero errors and warnings.
HTTP responses were scripted; no native model, weights, paid calls or native
failure-frequency measurements were used. Existing LiteLLM cleanup warnings
remain.
