# Keep truncated promotion targets from changing unrelated prices

The generated promotion target is limited to 80 characters, while store product
and shelf names can be longer. A clipped name was not an exact catalog name,
so scenario matching could fall through to shared-word matching. A reproducer
intended for only s-cola also discounted s-zero, s-large and s-beer: four products
instead of one. The existing multiple-products warning did not prevent those
unrequested price changes.

At the model field limit, the writer now restores a uniquely matching full
product or shelf name before checking or saving the target. Multiple matching
names, including a literal 80-character name sharing the prefix with a longer
one, cause that promotion to be omitted with an ambiguity warning. The prompt
describes this constraint. Keyword targets keep their existing scope, unrelated
valid promotions remain usable, and the existing exact/unique-case-insensitive
SKU precedence remains authoritative. No stock-out limits or domain target
limits were changed.

Forty-eight actual LiteLLM/Instructor HTTP cases cover both JSON modes, English
and Korean names, product and shelf targets, unique and ambiguous prefixes,
discounts and 1+1 promotions. They apply the returned scenario, check the exact
affected SKU set and untouched neighboring prices, preserve the source layout,
and repeat through cache. Nine controls preserve full 80-character names,
keyword scope, unknown/no-store behavior, repeated names, independent promotions
and exact/ambiguous SKU identity.

Before the fix, all 48 HTTP cases failed and five initial controls passed in
3.74 seconds. Development checks caught three SKU-precedence regressions in
the initial prefix handling; the guard was added before publication. The final
focused scenario suite passed 168 tests in 4.37 seconds. Full source Pyright
reported zero errors and warnings. There were 72 known LiteLLM asynchronous
logging cleanup warnings. HTTP replies are scripted; no native inference,
model downloads or paid calls ran.
