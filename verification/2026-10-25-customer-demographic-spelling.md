# Keep valid customer batches when demographic spelling varies

The generated-customer schema accepted only exact age and gender literals.
Answers such as `female`, `60S+` or a canonical value surrounded by Unicode
whitespace exhausted three attempts and caused TooManyBatchesFailed even when
every other field was valid. Supplied identity and purpose labels already
handled equivalent spellings, but the demographic literals did not.

A before-validator now uses the existing canonical-identifier resolver for
the six age groups and two gender values. It preserves exact values, trims
surrounding whitespace and accepts a unique case-insensitive match. Required
fields and their schema enums remain unchanged. Unknown values, numeric ages,
nulls, lists and blank strings are not guessed or defaulted. Domain Persona
validation and user/imported data handling are unchanged.

Seventy-two real LiteLLM/Instructor HTTP cases cover both JSON modes, every
age/gender pair and lowercase, uppercase and padded spellings. They run the
profile, traffic and customer-generation stages, verify canonical values,
gender-based IDs and arrival hours, require only one customer request, inspect
new cache contents and revalidate deliberately altered cached spellings.
Eleven invalid-value controls and one required-enum/exact-value control retain
the input boundary. All 72 HTTP cases failed before the production fix.
The schema control initially assumed inline enums; it was corrected to follow
the existing named definitions and passed against unchanged source.

The focused suite passed 208 tests in 8.27 seconds and exposed one pre-existing
test that still expected unsupplied identity/purpose labels to be accepted.
Executing the committed pre-change generator independently confirmed that it
already rejected those labels. That test now asserts the existing rejection
and failed-batch accounting; it passed separately in 1.81 seconds. In total,
209 distinct focused tests passed. Full source Pyright reported zero errors
and warnings. No native inference, model downloads or paid calls ran; model
replies are scripted and do not establish real-model failure frequency.
