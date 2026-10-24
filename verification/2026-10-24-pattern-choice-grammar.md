# Constrain local behavior selection to available pattern IDs

The behavior-selection prompt required an available pattern ID, but its schema
allowed any string and even omission. A grammar-capable local provider could
therefore return a translated name or invented ID while satisfying its grammar.
The engine's existing fallback then selected the first pattern, potentially
applying a purchase policy different from the intended browsing-only behavior.

Each request now has its own pattern-selection schema with an enum of the
available IDs and a required pattern_id in the transmitted JSON schema. Custom
IDs retain their exact spelling and length. Missing/unknown responses from
providers that do not enforce the schema retain the established runtime fallback;
this change does not turn those responses into additional model retries.
Optional explanation normalization and length bounds remain inherited. The shared
base response schema is not mutated, and request-local choices enter cache identity.

Twelve HTTP regressions failed before the fix and passed afterward. Their scripted
provider uses the transmitted JSON schema to determine whether an invented ID is
allowed; this tests the wire contract, not real model quality or a particular
server's grammar compiler. Coverage includes single/multiple choices, both route
orderings, long and multilingual custom IDs, purchase caps, checkout-free browsing,
and cache reuse. Additional controls cover missing/empty/unknown IDs from
non-enforcing providers and concurrent visits with different pattern catalogs.

Focused pattern, engine, product-limit, budget, optional-text, context-recovery,
impulse-scope and action-boundary verification passed 261 tests in 6.12 seconds.
Strict Pyright reported zero errors. The scripted clients were updated to accept
the request-local subclass while preserving their original behavior assertions.
No live or paid inference was used.
