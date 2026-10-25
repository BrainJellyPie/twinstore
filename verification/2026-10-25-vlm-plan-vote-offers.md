# Preserve the majority's resolved shelf offers in entry-plan votes

Entry-plan voting identified a candidate set only by its SKUs. When one SKU
stood on both Snacks at 100 and Milk at 700, a Snacks vote followed by two
Milk votes selected Snacks. Reordering the same members to put Milk first
selected Milk instead. Quantities from the minority offer also entered the
median because all three votes shared one key.

The identity now contains the sorted set of resolved offers: rack, block,
face, level and exact SKU. JSON encoding replaces separator joining, so a
literal `a|b` SKU cannot collide with separate `a` and `b` candidates. Candidate
order and duplicate entries do not affect identity. Empty matches retain the
existing unresolved-text path. The vote threshold, entering-plan eligibility,
quantity median, ties and seeded selection among an identical candidate set
are unchanged. No stored schema or model-response cache key changes.

Forty-eight real LiteLLM/Instructor HTTP cases cover both structured modes,
all six member orderings, reversed catalog order and shared or distinct SKUs.
They execute the resulting purchase and verify the majority's Milk location,
700 price, level 3, quantity 2 from its two supporters, total 1400, plan log,
cache reuse and untouched source. Seven controls cover order/duplicate
invariance, placement dimensions, exact SKU case and separator collisions.
Before the fix, 30 cases failed and 25 passed in 3.79 seconds.

The focused planning, voting, walkout, offer, basket and choice-weight suite
passed 353 tests in 21.18 seconds with 64 existing LiteLLM logging-worker
cleanup warnings. Full source Pyright reported zero errors and warnings.
Responses were scripted through the actual HTTP stack; no native model
inference, weight downloads or paid calls ran. The defect is in combining
already valid model choices, not a measured model-recognition error rate.
