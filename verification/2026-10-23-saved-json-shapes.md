# Recover browsing from wrong-shaped saved JSON

## Reproduction and change

`personas.json` containing `null`, a boolean or a number broke the entire project list with HTTP 500.
Strings/objects reached the frontend as customer lists. Non-object layout files similarly broke every
project containing them; mixed string/non-string metadata creation dates broke list sorting.

Check customer arrays before using them for readiness badges or returning them to the editor. Reject
non-object layout files through the existing named damaged-file error, allowing list readers to skip
them. Convert creation-date sort keys to strings. These reads leave all saved files unchanged and keep
healthy projects/layouts accessible.

## Evidence

- Matrix includes null, boolean, numeric, string, object and array containers, invalid date sort keys,
  unaffected healthy projects, and byte-for-byte preservation of damaged files.
- Initial new test run: 17 failed; the healthy-layout control used an incomplete old test fixture and
  assumed a nested GET response. Completed that fixture and corrected the response assertion before
  recording the production baseline: **16 failed, 1 passed in 3.32s**.
- New cases plus existing damaged-file and customer-validation modules: **70 passed in 3.45s**.
- Strict Pyright on the two changed modules: **0 errors** after adding a typing-only list cast.
- Separate seeded shared-store exploration tested 300 combinations of finite stock, crew, refill work,
  queue times, substitutions and simultaneous arrivals in 0.741s. No invariant failures were found;
  seed 1042326, scratch report `/workspace/scratch/shared-boundaries-exploration.json`.

No full suite, paid/live model calls, frontend changes or release binary changes. This fix addresses
the outer saved-file containers and sorting; it does not claim complete validation of every nested record.
