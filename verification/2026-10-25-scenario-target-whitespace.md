# Preserve exact promotion and stock-out scope for padded catalog labels

Scenario matching stripped the requested target but not the stored product,
shelf or category label. A correct model target such as Cola 500ml therefore
missed a stored name surrounded by Unicode whitespace and fell through to
shared-word matching. A concrete five-product store applied the intended
single-product discount to all five products. Stock-outs used the same matcher
and could remove unrelated products as well.

Exact-name indexes and comparisons now strip surrounding whitespace on both
sides. The existing case-insensitive matching remains in place; SKU matching
keeps its previous precedence and case-sensitive identity rules. Source catalog
names are not rewritten. The bounded-promotion name lookup also uses trimmed
labels so restoration and final scenario matching agree. Names that become
identical after trimming retain their shared scope rather than arbitrarily
selecting one SKU.

Thirty-six actual LiteLLM/Instructor HTTP cases cover promotions and stock-outs,
product/shelf/category labels, ordinary spaces, tabs/newlines, full-width spaces
and nonbreaking spaces, both JSON modes and cache reuse. They apply the scenario
and verify affected SKUs, untouched neighboring prices and source immutability.
Four controls cover padded long-name restoration and multiple SKUs sharing a
normalized name. All 40 new tests failed before the fix in 3.23 seconds.

The focused whitespace, bounded-target, existing target matching, shared-SKU
and reference-price suite passed 145 tests in 3.73 seconds. Full source Pyright
reported zero errors and warnings. There were 83 known LiteLLM asynchronous
logging cleanup warnings. The HTTP replies are scripted; no native inference,
model downloads or paid calls ran.
