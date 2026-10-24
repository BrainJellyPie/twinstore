# Keep valid visits when non-buy fields are unspecified

Models can emit null for a purchase SKU or quantity on an entry, movement, browse,
payment or exit, where neither value is used. Those values previously invalidated
the whole action response even when its real purchases were complete and valid.
The model boundary now maps only these non-buy nulls to the existing empty-SKU
and quantity-one defaults. Intent and impulse prompts explicitly ask for those
defaults instead of null.

Actual buy values, unknown action types, other non-null invalid types, navigation
requirements and authored domain actions retain their validation. The input
response is copied, and internal engine hints are still stripped. No purchase is
invented from an unspecified action or field.

The pre-fix run failed 26 regressions with 16 controls passing. HTTP cases cover
both structured modes, intent versus impulse, either/both null fields, the real
three-plus-one-unit purchases, one checkout, exit and cache reuse. Other cases
cover every non-buy action including an implicit action, invalid buy/type values,
and the unchanged domain boundary.

Focused verification covers 340 unique passing cases across action, budget,
offer, exposure, catalog/context recovery and pattern-text checks. The final 79
cases passed in 2.63 seconds after purchase quantity assertions were keyed by SKU
instead of assuming the route order. The production patch was unchanged after
the broad run, which emitted ten existing LiteLLM logging-cleanup warnings.
Strict Pyright reported zero errors. All responses were scripted; no live or paid
inference was used.
