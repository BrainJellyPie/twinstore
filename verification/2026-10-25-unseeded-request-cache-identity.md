# Preserve respondent identity when provider seeding is disabled

Study and simulation callers supply stable per-request seeds to distinguish
respondents and paired draws. LLMConfig.seed defaults to None, which deliberately
prevents sending a seed to the provider. The cache used only the effective
provider seed and therefore discarded those per-request identities as well.

With identical profile text and one request at a time, a two-person survey
received ratings [1, 1] from one cached draw instead of making two model calls.
Concurrent calls could initially return different ratings but wrote one shared
cache entry, so repeating the study changed earlier respondents to the final
cached answer. The survey application explicitly uses temperature 0.6 to permit
sampling; reusing one draw under different respondent IDs defeats that behavior.

When provider seeding is disabled and a per-request seed is supplied, the cache
now stores that value as a separate identity component. No seed is sent to the
provider. Enabled provider-seed behavior and keys, and requests with no seed
identity, retain their existing handling. An unseeded request cannot collide
with a seeded request that happens to use the same numerical seed. Existing
shared entries are not reused by the newly distinguished requests.

Eight actual LiteLLM/Instructor HTTP survey cases cover both JSON modes,
two/four identical-profile respondents, and serial/concurrent execution. They
check separate draws and cache entries, the resulting rating mean, exact repeat
stability, new requests after changing the study seed, and absence of seed in
the provider body. Seven controls cover synchronous/asynchronous clients,
enabled/disabled configuration seeds, absent request seeds and cross-setting
cache separation. Before the change, eleven tests failed and four passed in
2.63 seconds.

The focused cache, survey-choice, shelf-interest and numeric-measurement suite
passed 274 tests in 8.17 seconds without warnings. Full source Pyright reported
zero errors and warnings. Responses are scripted; separate model calls do not
guarantee different or statistically independent real-model answers. No native
inference, model downloads or paid calls ran.
