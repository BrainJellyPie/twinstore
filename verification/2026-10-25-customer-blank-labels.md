# Keep blank labels out of generated customer populations

A nonempty list containing empty or whitespace-only strings bypassed the
customer generator's empty-pool fallback. Those strings reached customer
identity/purpose grammars and hourly specifications as if they were real
traits. Blank hourly types similarly bypassed the existing missing-type repair.

Trim surrounding whitespace and discard blank labels after validating the
trade-area and hourly response fields. Preserve valid labels, their order,
internal whitespace, length limits and strict structure checks. All-blank
pools use the existing shopper/shopping defaults; hours with positive visits
and no usable types receive the existing trade-area fallback without changing
their counts. Prompts explicitly disallow blank labels.

Before the fix, 16 end-to-end cases failed and 20 malformed-input controls
passed in 2.98 seconds. Scripted HTTP responses exercise the real model client
in both JSON modes, including empty lists, empty strings, Unicode whitespace,
mixed multilingual labels and independently blank hourly types. They verify
Monday/Sunday customer counts, arrival slots, unique IDs, downstream prompts,
schema choices and cached repeat generation.

After the fix, 182 focused customer-label, traffic, calendar and identity
checks passed in 4.95 seconds. Pyright reported zero errors and warnings.
No native model inference or model download was used.
