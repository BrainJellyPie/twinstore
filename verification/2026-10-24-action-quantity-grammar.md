# Match generated purchase quantities to the execution ceiling

The executor limits each purchase line to the configured maximum, but intent and
impulse generation previously received neither that maximum in their prompts nor
a numeric bound in their output schemas. Local constrained decoding could produce
zero, negative or arbitrarily oversized quantities and leave execution to change
the requested purchase afterward. This change passes the existing configuration
to both stages and the focused intent path used after an input-context failure.

The schema carries a minimum of one and the configured maximum. These are grammar
constraints only: a provider ignoring the schema still reaches the existing runtime
clamp, without invalidating the whole visit. Standalone helper callers omitting the
optional ceiling keep their previous schema/prompt behavior. No new configuration
limit, model call, parser behavior or authored-domain restriction is introduced.

Eight HTTP regressions failed before the patch because the request schema lacked
the bound. The final tests cover limits 1, 2, 6 and 12, a changed limit using the
same client and cache, matching prompt instructions, planned and impulse checkout,
and non-enforcing responses containing a 101-digit quantity. Context recovery
tests inspect the full, focused and impulse requests. Related offer, budget,
exposure, cache and optional-field checks also pass: 225 cases in 9.31 seconds.
Two existing LiteLLM logging-cleanup warnings occurred. Strict Pyright reports
zero errors. All model responses are scripted HTTP responses; this verifies the
request contract and execution behavior, not live model quality or grammar-engine
performance. Extremely long integers were separately probed: values exceeding
4,300 digits are rejected by the current parser, so no cache-crash claim is made.
