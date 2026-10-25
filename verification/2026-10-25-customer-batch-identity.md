# Separate independent customer batches in the model cache

The writer numbered customer specifications from zero in every batch and sent
no batch identity. With one customer type, no keywords and a common arrival
hour, separate batches had identical prompts and schemas. The sequential probe
flow reliably cached five customers and reused them while claiming to write
fifteen independent customers. Ordinary batches also overwrote the same cache
entry, and changing the generation seed did not separate low-variation inputs.
Split recovery could give two identical child requests the same problem.

Every customer-writing prompt now carries its generation seed and daily sample
position range, explicitly identified as bookkeeping rather than customer
traits. The position is propagated into bounded recovery children. A probe
reserves its entire requested range before the remaining generation starts,
even if a child returns fewer customers: reserving only its actual output count
could reuse the later child's cache. A concrete five-customer short-probe case
otherwise returned only three written customers and filled two with twins.

The prompt identity works when the local provider ignores or does not support
the seed parameter. The change preserves the customer schema, arrival hours,
IDs, existing sample/twin handling, request limits and one-level recovery.
Distinct batches now perform their intended model calls; they no longer save
time by incorrectly treating cached customers as newly written people. Repeating
the same inputs and seed still hits the corresponding completed-batch caches.
Existing saved customers are not regenerated or rewritten automatically.

Forty-eight actual LiteLLM/Instructor HTTP cases cover both structured modes,
batch sizes two and five, ordinary generation, full and sampled probe flows,
short probes, context rejection and truncated output. The provider receives no
seed parameter in these cases. Checks cover written counts, unique batch-derived
descriptions, population IDs, arrival times, request plans, repeat-cache
stability and separation after changing the generation seed. The first 36
cases failed before the change; an additional four short-probe recovery cases
exposed the need to reserve the full requested range.

The focused generation, concurrency, probe-budget, short-response and recovery
suite passed 244 tests in 18.75 seconds with 13 existing LiteLLM logging cleanup
warnings. Full source Pyright reported zero errors and warnings. Scripted
responses encode the request identity to demonstrate cache separation; this
does not guarantee semantic diversity from a real model. No native inference,
weight downloads or paid calls ran.
