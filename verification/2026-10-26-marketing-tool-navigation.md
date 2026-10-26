# Marketing tool links after v0.8.2

Integrate the interface branch through `0d790dae`, including `a1462bd8`:
the command palette searches the eleven studio tools across six languages
and opens `/marketing/<store>?tool=<id>`.

A new real-router regression exposed a repeat-navigation failure. Open the
shelf tool link, choose the A/B tab, then open the same shelf link again:
the URL had never changed and the history-entry key stayed unchanged, so
the page retained the A/B tab. The test failed at the second shelf selection.

The route now supplies the selected tool to the page and tab selection
replaces the search parameter. The page stays mounted while changing tools;
project changes still reset its state. Pending question/experiment drafts
use the same tab-change callback. A standalone page retains local tab state.
The navigation tests also cover changing projects with a requested tool and
preserving a subsequent tab selection across a query refresh.

Validation:

- Before: the existing five related UI files passed 97 tests. Added navigation
  cases produced one failure and 15 passes in the route suite.
- After: all 99 tests in those five files passed, including command palette
  questions/ownership, real-router marketing navigation and localized screens
  (12.77 s). The targeted route suite also passed all 16 cases.
- TypeScript checking and the production build passed. ESLint on the six
  changed TypeScript files reported no errors and one route fast-refresh
  warning, reproduced on the unmodified upstream route as well.
- Backend code is unchanged from verified main `e1f980bd`; its tests were not
  rerun for this interface-only integration. Diff checking passed.
- All changelog content from v0.8.2 onward is byte-for-byte unchanged. This
  integration belongs to Unreleased and does not alter the published tag.
