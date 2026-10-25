# Keep a survey reference price attached to its intended image

The concept-test designer drops missing or ambiguous image names. When the
first proposed image was dropped, its reference price remained and was shown
to respondents as the next product's price. The draft now clears that price
and adds a warning. Other products, question choices, context and quotas stay
intact. A resolved first image retains its price even if later images fail;
an explicitly unassigned draft with no image choices keeps its editable price.

Seventeen failing regressions reproduced the issue before the fix: sixteen
real LiteLLM/Instructor HTTP cases and one public design API case. HTTP cases
cover JSON/JSON Schema, USD/KRW, missing/ambiguous first names and reversed
library order. They pass the resulting SurveyRequest to the real survey
engine and inspect the respondent request to ensure the removed product's
price is not used. Successful responses, remaining identities, quotas,
unchanged library input and cached repeats are verified. Controls cover
duplicates, decorated/case-insensitive names and absent prices/images.

Focused reference-identity, price-boundary, choice-spelling, optional-field
and API suites: 182 passed in 4.24 seconds. Full-source Pyright: zero errors
and warnings. The HTTP provider is scripted; no native inference, model
download, paid call or model error-frequency measurement was performed.
Existing LiteLLM logging cleanup warnings remain.
