# Correct contradictory price-sensitivity answers before caching

Survey response fields checked each price independently, allowing contradictory
thresholds such as expensive=4 and too_expensive=3. These responses were cached
and counted as successful. Price analysis later discarded them, so a five-person
survey could report success while lacking its requested price analysis.

The model response now validates too_cheap <= cheap <= expensive <= too_expensive
within the existing two-attempt correction loop, before caching. The prompt
states this order explicitly. Do not sort or invent the respondent's prices.
Repeated failure uses the existing respondent-error path and preserves other
respondents. Equal thresholds, including zero, remain supported; questionnaires
without price questions have no new field requirements. Historical/authored
answer aggregation retains its existing consistency filter.

Before the fix, 36 inverted-price cases failed and five controls passed in
4.22 seconds. Scripted HTTP covers both JSON modes, USD/KRW conversion, each
adjacent inversion, corrected/repeated failures, legacy cache revalidation,
later recovery and cached repeats. A real five-person panel and report verify
respondent/error counts, preserved intent ratings and recovered price analysis.

After the fix, 156 focused survey, numeric-boundary, price-analysis and study
response checks passed in 8.90 seconds. Full source Pyright reported zero errors
and warnings. No native model inference or paid model calls were used.
