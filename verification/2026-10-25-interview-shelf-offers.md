# Retain distinct offers in shopper interview evidence

Journey construction deduplicated viewed shelf products by SKU alone. A
second placement of the same SKU with a discount or other offer disappeared
from interview evidence. Changing only that placement left the prompt and
cache identity unchanged, even though the shopper visited the relevant face.

Deduplication now uses the SKU and every displayed offer field: name, price,
regular price and promotion. Exact copies still collapse. Existing visited
face filtering and the bounded shelf context continue to apply.

Thirty-four regressions cover actual executed browse trips, JSON/JSON Schema,
USD/KRW, interview answers/follow-ups, each differing offer field, duplicate
facings and reversed order. The HTTP tests verify both offers reach prompts,
changing the second offer requests a new answer, repeats reuse cache, unseen
faces stay excluded, and source stores/customer timelines remain unchanged.
The initial answer tests compared Instructor's private response metadata;
after comparing public model fields instead, all sixteen answer cases also
reproduced the missing-offer defect before the source change.

Focused offer, personal-context, direct-purchase, optional-annotation and
interview API suites: 137 passed in 6.67 seconds. Full-source Pyright: zero
errors and warnings. Real LiteLLM/Instructor used scripted HTTP responses;
there were no native-model runs, weight downloads or paid calls. This checks
evidence and cache correctness, not native model error frequency. Existing
LiteLLM logging cleanup warnings remain.
