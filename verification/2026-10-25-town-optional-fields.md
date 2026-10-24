# Keep known neighborhood settings when optional suggestions are null

A local model could correctly identify a university area and its rival count
but return null for an unspecified label, rationale, neighbor list or numeric
estimate. Those optional values invalidated the whole draft and the describe
API returned 502, even though omitting them already used declared defaults.

Normalize null optional text to empty strings and null neighbor lists to [].
For size, density and venue density, use the same declared defaults as omission.
Keep explicit values, including zero rivals, and leave an unknown rival count
as None. Required archetypes, malformed non-null values and numeric limits stay
strict. The prompt specifies the expected empty/default values.

Before the fix, 30 cases failed and 20 controls passed in 6.29 seconds.
Scripted HTTP covers both JSON modes, each optional field and all together,
zero/two rival counts, retained settings, normalized cache contents and repeat
calls with a different town-generation seed. API tests pass the returned spec
into actual neighborhood generation. Controls retain required-type validation,
numeric bounds and explicit competitor endpoints.

After the fix, 80 focused draft, API, numeric-validation and town-generation
checks passed in 6.26 seconds. Full source Pyright reported zero errors and
warnings. No native model inference or paid model calls were used.
