# Preserve A/B draft placement and price evidence

The experiment prompt indexed its product listing by name alone, retaining
only the first shelf, height and price. A repeated product's other offers were
invisible. Editing a nonfirst offer could leave the prompt unchanged and reuse
an older cached draft despite changed control-layout evidence.

Listing identity now includes SKU, name, rack, level and price. Exact copies
at the same placement collapse; distinct offers remain eligible for the
existing relevance ordering and 150-entry limit. A single explanatory line
states that sales figures are totals per SKU across all shelves, so repeated
placements are not additional sales. Variant application and the meaning of
price, discount and placement changes are unchanged.

Eight real SDK/Instructor/HTTP cases cover two JSON modes, USD/KRW and reversed
rack orders. Three offers for one SKU retain their own prices and heights,
identical copies appear once, a changed nonfirst price changes the prompt/cache
identity, repeated unchanged requests use cache, and source stores remain
unchanged. A 190-product boundary control retains a specifically requested
late product while limiting the final listing to 150 entries.

After correcting the fixture's starting shelf level to its explicitly tested
level 1, the pre-repair reproduction had 8 failures and 1 passing cap control
in 2.47 seconds. The final focused draft API, target, catalog-specificity and
offer tests all pass: 101 in 4.87 seconds. Full-source Pyright reports zero
errors and warnings. Tests emit 27 existing LiteLLM logging coroutine warnings.
No full suite, paid calls, weights or native inference were used. Scripted
responses verify evidence transmission/cache behavior, not native model
decision quality; drafts still require review in the builder.
