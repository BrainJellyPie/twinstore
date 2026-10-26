# Keep experiment labels in reports and storefront names with shoppers

Integrated `claude/online-shopping-features-ji7y0f` through `0fb179ca`
onto main `cad63a72`. Incoming work gives Shelf Lab a keyboard-usable
product selector, keeps captured facings within the API's 1–24 range and
shows online variants under the original family's storefront name. The
variant designer explains the distinction in all six UI languages.

Integration review reproduced two missing paths in the incoming name
change: clickstream CSV rows lost each variant's report label, and a
variant selected as the rival still exposed its experiment label in the
shopper's page URL/name. Both API regressions failed before the repair.

Rivals now use the same shopper-facing family-name resolution as tested
stores. Their original report label is retained in run status, with an
optional/defaulted field for compatibility. Results, session metadata and
CSV exports use labels captured when the run started; snapshots, shopper
prompts and replay rendering use what shoppers saw. The CSV retains each
variant's label while session URLs keep the storefront name. Live renames
after the run do not rewrite historical labels or sessions. Older rival
snapshots without a separate status label retain their snapshot-name
fallback. These changes do not mutate the saved live store names.

Verification passes 33 backend API cases across six files in 42.33 seconds,
covering real rule-policy runs, rival routing, captured imagery/replays,
interviews and transfers back to physical layouts. The two targeted cases
pass after previously failing with valid requests (7.24 seconds before,
7.39 seconds after); the initial invalid max_steps fixture was corrected
before that baseline and is not counted as a product failure.

Frontend verification passes 88 cases across seven files in 21.75 seconds,
including Shelf Lab selection, facing limits, unsaved capture changes,
apply lifecycle, currency edits, online design/launching and rival reports.
TypeScript, strict Pyright, server boot and lint of all eight changed
TypeScript files report no errors/warnings. Production build passes in
21.33 seconds with existing large-chunk and Babel-timing notices. Diff
checks pass. No manual browser/device or new model-inference coverage is
claimed for this integration. The preceding capture repair retains its
six passing actual CPU checks and 1,744 capture cases; that engine code
is unchanged here.

Only Unreleased changelog entries conflicted; both sides are preserved.
Released changelog text and v0.8.2 tag/assets remain unchanged.
Logs: `/workspace/scratch/variant-name-{before-valid,core-tests,backend-tests,frontend-tests,pyright,boot,tsc,eslint,build}.log`.
