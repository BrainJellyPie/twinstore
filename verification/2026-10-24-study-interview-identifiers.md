# Neighborhood study and interview identifiers

Neighborhood synergy jobs and saved group interviews used six hexadecimal UUID
digits. Distinct UUIDs sharing that prefix wrote the same status/transcript
path. A new study could inherit a previous result, and a new interview replaced
the previous transcript in the saved history.

Both families now use full UUIDs. Synergy registration exclusively creates its
output directory before writing or submitting work. Group interview persistence
checks its destination while holding the existing project tree lock, which
serializes group commits, before the atomic JSON write. An occupied destination
returns HTTP 409 and leaves existing data unchanged.

Validation was entirely offline:

- 12 new cases cover matching prefixes, occupied full IDs and preservation/read
  support for old short IDs. Neighborhood tests include explicit and inferred
  layouts; interview tests include ordinary and path-like Unicode customer IDs.
  All 12 failed before the fix.
- 72 focused identifier, project lifecycle, input snapshot and interview API
  tests passed in 10.78 seconds. Model responses and queued work were mocked.
- Strict Pyright on both changed modules: zero errors.

No old records were migrated. Ordinary simulation run registration already
rejects an existing directory under its run lock and was left unchanged.
