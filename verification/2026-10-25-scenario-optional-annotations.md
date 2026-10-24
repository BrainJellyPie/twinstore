# Preserve scenario operations when optional annotations are null

Null notes, an event's note or a promotion's label rejected an otherwise valid
model-produced scenario. A missing comment could therefore discard its actual
weather, weekday restriction, promotion and stock-out settings.

Normalize only those three optional text fields to their existing empty-string
defaults and state that convention in the prompt. Keep required values,
non-null malformed text, bounds and operational list validation unchanged.
In particular, null weekdays do not become an unrestricted all-day scenario.

Before the fix, nine cases failed and 37 controls passed in 4.62 seconds.
Scripted HTTP covers both JSON modes, each annotation and all together,
null/omitted/explicit Korean text, exact discounted SKU/price, removed stock,
event hours, Friday-only customer selection, source immutability and cache hits.
An API test verifies preserved scenario settings and compiled effects.

After the fix, 113 focused model, weekday, target and scenario API checks passed
in 4.36 seconds. Full source Pyright reported zero errors and warnings. No native
model inference or paid model calls were used.
