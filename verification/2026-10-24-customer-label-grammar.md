# Preserve shared labels in generated customers

Customer-writing prompts required identities and purposes from the trade-area
profile, but their schemas allowed arbitrary strings. A constrained local decoder
could therefore invent cohort labels even when it followed the schema. Each day's
persona response now carries the exact supplied identity/purpose enums, with
duplicate choices removed and the existing shopper/shopping fallback for empty
pools. Runtime behavior for non-enforcing providers is unchanged.

The constraints are inline strings with the existing 120-character limit. This
matters for llama.cpp: common/json-schema.cpp at revision
6b9ba4f2e8c1436511956f0b3c309e2c9e642071 resolves a $ref before checking enum siblings.
An enum next to the reusable PersonaLabel reference would be ignored by that
converter. HTTP tests assert inline bounds and enums. This compatibility check was
source inspection, not a compiled/native model run.

Ten pre-fix HTTP cases demonstrated invented labels reaching the final population.
Checks cover both structured modes, repeated labels, Korean/Japanese/accented text,
quotes/backslashes/newlines, maximum-length labels, empty pools, a changed profile,
cached reuse, stable IDs and absence of unintended twins. Related batch splitting,
truncation, count bounds, optional fields, budgets, traffic and missing-day cases
also pass. Test doubles that constructed the old nested model now return JSON
fields, matching the production transport.

348 distinct focused checks passed across the affected files. After the final
inline-schema adjustment, 109 relevant checks passed in 3.24 seconds; strict
Pyright reports zero errors. A known LiteLLM logging coroutine cleanup warning
was emitted. All responses were scripted; no paid or live model inference ran.
