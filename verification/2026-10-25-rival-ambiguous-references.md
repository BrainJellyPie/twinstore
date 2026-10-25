# Do not choose a rival reference SKU or price by shelf order

The reference catalog kept only the first row for each normalized product
name. With Tea priced at 100 and 400 minor units and a rival price of 200,
reversing the shelves changed the index from 2.0 to 0.5 and the suggested
pull from 0.67 to 1.5. This happened both for two SKUs sharing a name and for
one SKU offered at different shelf prices.

Names now retain their SKU identities and distinct reference prices. A name
shared by multiple SKUs cannot establish a product match, including through
an alias; it is excluded from the model's eligible reference names. A known
single SKU with multiple prices may count toward assortment overlap, but
does not supply an arbitrary reference price. Identical repeated offers and
unambiguous neighboring products continue to compare normally.

Thirty reproduction checks failed before the change and nine controls passed.
The focused comparison/API suites now pass 167 checks in 5.18 seconds.
Full-source Pyright reports zero errors and warnings. Cases cover reversed
order, normalized Unicode-width names, exact and explicit-alias matches,
same/different prices and SKUs, repeated identical copies and healthy mixed
assortments. Six API cases verify an ambiguous-only comparison leaves the
saved town and pull history unchanged even when apply=true.

No native model inference, weights or paid calls were used. The change is
deterministic validation of product references; existing scripted model-match
tests also pass. Third-party LiteLLM logging cleanup warnings remain.
