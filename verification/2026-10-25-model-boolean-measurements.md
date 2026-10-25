# Keep boolean model answers out of numeric measurements

Permissive numeric validation accepted JSON booleans as numbers. Direct probes
turned an appeal rating of true into 1, price thresholds of false/true into
0.0/1.0, pick=true and noticed=[true] into product badge 1, and receipt
quantity=false and unit_price=true into 0.0 units at 1.0 currency unit. Such
values can corrupt demand, product selection and study metrics. Strict initial
parsing already rejects some of these inputs, but the cache also uses Python
model validation and must independently enforce the same meaning.

Engine response validators now reject booleans before numeric conversion for
survey ratings/prices, shelf choices and noticed badges, shelf interest and
badge numbers, storefront ratings, and receipt quantities/amounts. Prompts
explicitly request numbers rather than true/false. Their changed text also
changes cache identities: entries previously converted to indistinguishable
ordinary numbers are not reused by these requests. Saved reports and receipts
are not rewritten. Valid zero values, numeric strings, optional explanations
and unknown receipt amounts retain their existing behavior. Error propagation,
panel exclusion and retry limits are unchanged.

The new harness covers 84 actual LiteLLM/Instructor HTTP cases: both JSON modes,
both boolean values and 21 numeric fields across the affected workflows. It
checks unsuccessful results are excluded rather than counted as refusals or
low ratings, invalid responses are not cached, a subsequent valid response
succeeds, repeated valid responses hit cache, and boolean cache entries are
revalidated and replaced. Seven controls exercise numeric values, existing
numeric-string handling, null receipt amounts and internal default glances.
The shelf arms have distinct prompt names so their cache entries are separate.

The focused suite passed 444 tests in 13.04 seconds with 48 existing LiteLLM
logging cleanup warnings. Following a type annotation adjustment to the badge
validator, its eight HTTP cases passed again in 2.33 seconds. Full source
Pyright finished with zero errors and warnings. Responses are scripted: this
verifies the harness and result handling, not the frequency or semantic quality
of real local-model responses. No native inference, weight downloads or paid
calls ran.
