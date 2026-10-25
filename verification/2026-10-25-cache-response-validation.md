# Apply the fresh-response contract when reading model cache

Instructor's fresh structured-response boundary uses strict JSON validation.
The cache instead called permissive Python model validation. An entry that a
fresh response would reject could therefore become a valid cache hit: true
became quantity=1, a numeric string became a count or coordinate, and a string
boolean changed an entry decision. In an actual HTTP/cache/action-execution
reproduction, replacing a cached purchase quantity with a boolean changed the
trip from three units at 300 cents to one unit at 100 cents.

Cache reads now pass the nested result through strict JSON model validation.
Using JSON mode preserves the normal wire representations of tuple fields,
enum values, dates and decimals; strict Python validation would incorrectly
reject some valid serialized values. Invalid entries follow the existing cache
miss path, request a new answer and are replaced only by a successful answer.
Cache identities, usage accounting and valid cache reuse are unchanged. This
does not attempt to infer whether an ordinary, correctly typed historical value
was originally derived from an incorrect model answer.

Thirty-two actual LiteLLM/Instructor HTTP cases cover both JSON modes, both
route orders and eight invalid cached action values. They verify strict fresh
validation rejects the same payload, a new answer is fetched, the resulting
trip buys three units for 300 cents, and the replacement cache is reused.
Ten synchronous/asynchronous checks also cover counts, booleans, coordinates
and valid JSON representations of tuples, enums, datetimes and decimals.
Before the change, 40 tests failed and two valid controls passed in 3.52 seconds.

The focused cache, action, generated-demographic, numeric-measurement and
capture-identity suite passed 441 tests in 10.74 seconds with eight existing
LiteLLM logging cleanup warnings. Full source Pyright reported zero errors
and warnings. The responses and invalid cache entries are scripted; no native
model inference, model downloads or paid calls ran.
