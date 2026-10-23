# Validate saved populations before starting work

The API already validated new customer IDs, but saved customer readers did not. Two saved customers
sharing an ID both passed a maximum-customer cap of one, and ID-keyed result maps can retain only one
of them. Blank IDs also launched runs. Invalid records produced HTTP 500 during run starts, and null
containers broke estimates before any useful error could be returned.

Share the existing identity rule with a validated storage reader used by simulations, estimates,
optimization, Shelf Lab/marketing and town synergy. Validate the whole population; never drop or rename
individual customers. Invalid files produce an actionable application error before job registration.
Missing and empty populations retain each caller's existing handling. Valid optional-field defaults and
exact IDs (including leading zeros, case, Unicode and surrounding spaces on nonblank IDs) remain intact.

Focused evidence:

- Eleven damaged-data variants across run starts, estimates, optimization and the shared customer-study
  reader; also verify no submitted jobs, pending state, source-file changes or customer-cap violations.
- Corrected two test fixture mistakes (the optimization minimum and a misspelled helper) before recording
  the baseline: **38 failed, 10 passed in 3.57s**.
- New cases plus existing identity validation and run estimates: **60 passed in 3.63s**.
- Strict Pyright on eight changed modules found three obsolete imports; after removing them, the final
  check of the affected modules reported **0 errors** (the other six were already clean).

No live model calls, full suite, frontend or release binary changes. Existing saved files and historical
reports are not migrated. This change validates job inputs; project browsing does not newly validate every
nested customer record.
