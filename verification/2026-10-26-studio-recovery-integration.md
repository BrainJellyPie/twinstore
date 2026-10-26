# Studio recovery, file-review focus and complete names

Integrate the interface branch through `bfdac439`. Its three new changes are
model-setup recovery after a studio study cannot start, result focus/scrolling
for file reviews, and hover titles for names shortened on screen. The branch
also merged earlier main history, which is not counted as new work.

Changelog conflicts were resolved under Unreleased. Backend files are
byte-for-byte unchanged from main `870a797d`. The recent multipack-rate guard
and mixed category/SKU online-transfer eligibility fix remain intact. Released
changelog content from v0.8.2 onward is unchanged.

All **129 tests across eleven related UI files** passed in 13.57 s, covering
study/draft ownership, online transfer, price/unit/inventory/pilot reviews and
localized studio screens. TypeScript checking and the production build passed
(20.47 s; existing chunk/plugin warnings). ESLint checked all 31 changed
TypeScript files with no errors and two home-route fast-refresh warnings;
both warnings were reproduced on the unchanged parent version of that route.
Diff checking passed.

Application code changed only in the frontend. Previously green backend
checks were not repeated, and no new model inference or model download is
claimed by these UI tests. This cycle integrates and verifies the upstream
changes without claiming an additional newly discovered production bug.
