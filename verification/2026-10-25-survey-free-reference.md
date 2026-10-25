# Free survey reference prices — 2026-10-25

Automatic concept-test conversion treated an explicit zero reference price as
missing, although the request schema, form and survey prompt support zero. The
price anchor disappeared before respondents saw the survey. The converter now
retains zero and negative zero as the free offer. Null remains unspecified, and
positive amounts too small for the currency's minor unit remain omitted with a
warning. If image A cannot be resolved, its reference price is still removed;
zero cannot move to a different product. The design prompt distinguishes zero
from null explicitly. The older boundary assertion for zero was corrected to
match the public request and form behavior.

Validation: corrected baseline 18 failed, 16 passed in 3.16s. All 34 new SDK and
identity cases passed after the change (2.97s), covering native Ollama/OpenAI,
JSON/JSON-schema, USD/KRW, zero/negative zero/null/tiny positive amounts, the real
survey prompt and cache reuse. 105 existing boundary/reference/optional-field
cases also passed: 139 distinct backend cases verified. Six existing survey
price-form draft tests passed in 4.97s (58 unrelated cases filtered out). Full
backend Pyright: 0 errors, 0 warnings; server boot passed. No live inference.
