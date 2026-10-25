# Free shelf and A/B prices — 2026-10-25

Automatic shelf and A/B design discarded explicit zero prices even though the
request schemas, forms and variant application support free offers. Conversion
now retains zero and negative zero, with prompts distinguishing a free offer
from an omitted price. Positive values that round to zero, nonfinite amounts
and unsafe integers remain rejected or omitted with the existing warnings.

The actual SDK baseline reproduced 32 failures and 32 passes in 3.89s. All
188 focused backend cases passed after the fix (4.15s), including both providers
(OpenAI-compatible and native Ollama), JSON/JSON-schema, USD/KRW, zero/negative
zero/null/tiny positive amounts, cache reuse, and actual application to a copied
store with its original reference price retained. Two additional cases verify
that a free price alone is an applicable design. Existing identity, rounding,
model recovery and optional-field tests also passed. Twelve frontend draft-price
round-trip cases passed in 5.45s (52 unrelated cases filtered out). Full backend
Pyright: 0 errors, 0 warnings; server boot passed. No live inference. The SDK
logging cleanup warnings are unchanged.
