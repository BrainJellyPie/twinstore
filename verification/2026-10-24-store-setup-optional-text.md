# Do not discard a store draft for unspecified text

The store-form writer allowed omitted text fields but rejected explicit null
values. Local models can reasonably use null for an address that the description
does not give, especially because nearby opening-day/hour/currency fields are
nullable. After two failed structured attempts, the form endpoint returned HTTP
502 and discarded otherwise usable hours and currency.

Only the five optional text fields (name, description, address, format and
rationale) now map null to their existing empty-string defaults. The prompt
distinguishes unspecified text from nullable days, hours and currency. Length
bounds, invalid non-text values, opening-window validation and ambiguous/unknown
format warnings remain unchanged. The form remains a reviewable draft; this
operation does not save a store or invent missing information.

Before the fix, ten real HTTP structured-response cases and five API regressions
failed; 38 omission/type/existing API controls passed. Final focused verification
passed 882 tests in 4.04 seconds, including the existing opening-hour boundary
matrix, with zero strict Pyright errors. Both JSON modes preserve the remaining
draft fields and reuse one successful request from cache. Nineteen existing
LiteLLM logging-cleanup warnings occurred. All model responses and transports were
scripted; no live or paid inference was used.
