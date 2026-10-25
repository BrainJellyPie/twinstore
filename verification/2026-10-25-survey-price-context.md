# Send the reference price to every concept-test questionnaire

SurveyRequest accepts a reference price independently of question choices,
but the respondent prompt included it only with price_vw. Value, purchase
intent, preference and open-only surveys silently ignored that price. Their
prompts and cache keys were identical across price changes.

The survey engine now explicitly gives product A's price when price_vw is
absent. Existing price-sensitivity questionnaires already include the price
and keep their wording. Other products are not assigned the reference price.
An omitted price adds no statement; an explicitly entered zero remains shown.

Twenty-four real LiteLLM/Instructor HTTP tests cover six question sets,
JSON/JSON Schema and USD/KRW. Each runs a low price, high price, zero and no
price, then repeats all four. Before the fix sixteen cases reused one answer
across all prices; the eight price_vw controls already passed. Afterward each
distinct price reaches the provider once, only identical repeats hit cache,
and scripted price-dependent responses survive into survey results/reports.
Persona inputs, product B ratings and currency conversion are checked.

Focused price-context, reference-identity, preference-spelling, open-answer
and currency API suites: 126 passed in 5.35 seconds. Full-source Pyright:
zero errors and warnings. Tests use a scripted provider, not native model
inference; they establish prompt/cache correctness, not measured shopper
behavior or native model failure rates. No weights or paid calls were used.
