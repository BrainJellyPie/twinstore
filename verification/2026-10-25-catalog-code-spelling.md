# Keep compact-code spelling from breaking context recovery

When a store's full action prompt exceeded the local model context, the engine
asked for a small list of offer codes before retrying the plan. A model returning
`@p1` or a padded `@P1` for the supplied `@P1` failed both shortlist attempts,
so the otherwise recoverable visit stopped before purchase planning.

The candidate-list validator now restores exact supplied codes from unique
case/whitespace variants before checking membership, deduplicating and caching.
It shares the identifier helper already used by starter selection, moved to the
existing prompting utilities. Unknown and ambiguous codes still fail. Exact
IDs win before trimmed or case-folded matching, and grammar enums are unchanged.

This normalization applies to the `codes` shortlist field only. Purchase-action
SKU interpretation, offer binding, exposure checks and alias-prefix collision
handling retain their existing behavior. A canonical SKU that resembles a code
must not be reinterpreted as a different purchase.

Thirty-six real LiteLLM/Instructor HTTP cases trigger the context-overflow path
and then return lowercase, padded or mixed shortlist codes. They cover both
structured modes and route orderings, ordinary SKUs, an exact `@P1` SKU collision
and a different product whose SKU is `@p1`. Every recovered visit must select
the intended offer, spend exactly 200, buy two units, pay once and exit; repeat
calls reuse the valid shortlist and plan caches. Two controls preserve unknown
and ambiguous-code rejection, distinct exact codes and shortlist deduplication.

Before the fix, 37 tests failed and one passed in 6.83 seconds. The focused code,
starter-identifier, missing-selection, compact-action and compact-impulse suite
passed 153 tests in 9.93 seconds. Full source Pyright reported zero errors and
warnings. No native inference, model downloads or paid requests ran. The HTTP
replies and context rejection are scripted, while parsing, cache handling,
planning and trip execution use the real application code.
