# Field-pilot commits and project deletion

Pilot creation did not participate in the project transaction, and imports and
closure only held a pilot-local lock. Project deletion could therefore remove
their inputs mid-request, acknowledge deletion while a write was pending, or
have a late write recreate a partial project directory. Twelve deterministic
overlap/lock cases failed before the fix.

All three mutations now acquire the existing project tree guard before their
commit work. Imports and closure acquire their local lock after the tree guard,
preserving optimistic revision checks and atomic import-history publication.
Creation also protects its source-study snapshot against deletion. The original
project-ID validation runs before constructing a lock path.

Validation:

- 18 new cases cover deletion during input reads and writes, deletion winning
  first, project lock contention with byte-for-byte preservation, source-study
  deletion in both orders, and invalid project IDs.
- All 39 lifecycle and field-pilot API tests passed in 7.24 seconds. Existing
  concurrent imports, stale revisions, irreversible closure, failed atomic
  commits, audit history and read-only analysis/export checks remain covered.
- Strict Pyright passed for the changed application module.

Tests use isolated temporary projects and synchronization events. No model
calls or real project deletions were used. Ordinary read-only pilot views are
unchanged.
