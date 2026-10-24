# Enforce supplied customer labels after model output

Customer identity and purpose were limited to the supplied profile in the JSON
schema and prompt, but the Python response model accepted any string. A model
ignoring the grammar, or an old invalid cache entry, could therefore persist
blank or invented customer labels and change the generated population's meaning.

Validate both fields inside the task-specific response model, before acceptance
and caching. Preserve exact supplied labels; trim outer whitespace and normalize
case only when there is one unambiguous match. Unknown, blank or ambiguous values
receive the existing three-attempt correction budget. Keep inline grammar enums,
empty-pool shopper/shopping fallbacks and internal/authored Persona compatibility.

Before the fix, all 42 new cases failed in 3.58 seconds. Scripted HTTP covers
both JSON modes, both fields, empty/Unicode-whitespace/unknown values, correction,
repeated failures, legacy caches, later recovery and cached repeats. Controls
cover unambiguous normalization, exact case-colliding labels, ambiguous variants,
Korean labels and empty-profile defaults. Assertions retain customer count,
arrival hour and absence of substitute twins.

After the fix, 220 focused label, generation, optional-field, budget, concurrency
and context/truncation-recovery checks passed in 7.33 seconds. Full source Pyright
reported zero errors and warnings. No native inference or paid model calls were used.
