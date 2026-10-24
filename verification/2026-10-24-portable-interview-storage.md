# Portable shopper interview storage

Accepted customer IDs such as `CustomerA` and `customera` were used as literal
transcript filenames. On case-insensitive filesystems they resolved to the same
record, so the second customer read and appended to the first customer's history.
Their locks were already distinct digests, allowing those colliding writes to
run concurrently. Windows device names such as `CON`, `NUL` and `COM1` could
also fail when saving a completed answer.

All new transcript filenames now use SHA-256 of the exact customer ID in the
existing `interviews/by-id` namespace. Legacy literal files remain readable when
their embedded customer and run identifiers match exactly. Reset removes only
the matching legacy record and the customer's digest record. Damaged current
records can still be reset; a damaged legacy record with unknown ownership stays
untouched, with an empty digest record overriding it for the requested customer.
Existing valid records migrate on the next saved answer or suggestions. Historical
records already overwritten by another customer cannot be reconstructed.

Verification:

- Seven failures before the change: case aliases, reserved Windows names and
  legacy ownership. The offline filesystem adapter models case-insensitive lookup
  and Windows reserved filenames; it is not a native Windows filesystem run.
- 97 focused checks passed in 17.74 seconds across interviews, encoded paths,
  arbitrary IDs, project deletion, concurrency and suggestion races.
- Two additional damaged-record reset cases passed with the focused nine-case
  regression module (3.57 seconds). Total distinct checks: 99.
- Strict Pyright on the changed module: zero errors. No paid/live model calls.

```sh
uv run pytest -q tests/server/test_interview_portable_storage.py tests/server/test_interview_customer_identifiers.py tests/server/test_shopper_id_paths.py tests/server/test_interview_api.py tests/server/test_interview_project_lifecycle.py tests/server/test_interview_concurrency.py tests/server/test_interview_suggestion_races.py --tb=short
uv run pyright src/store_emulator/application/interview.py
```

This change is prepared after the pinned v0.4.12 candidate and will be published
to main after that release finishes.
