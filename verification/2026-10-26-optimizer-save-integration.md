# Optimizer save focus and delayed completion

Integrated `claude/online-shopping-features-ji7y0f` through `997464d8`
onto main `0a982c31`. Its saved-layout focus change continues keyboard
navigation from the new layout's tab when the optimizer closes, for both
rule and vision judgments.

Review reproduced a separate delayed-response bug: completing a save after
the dialog closed, its view unmounted or another layout was selected still
changed the global selection to the saved layout. The save now captures
the initial selection and checks that the same view remains active and
the selection is unchanged after refreshing the layout list. A completed
save still invalidates its original store's list; leaving the view only
prevents unwanted navigation. Normal save-and-open behavior and focus remain.

The three new delayed-response regressions fail on the incoming branch;
18 existing cases pass. Final focused coverage passes 70 distinct cases
across optimizer results, optimizer model selection and layout navigation.
The initial type check rejected the test's ES2024 `Promise.withResolvers`
helper because this project targets an earlier library. Replacing it with
an ordinary deferred Promise fixed the test compatibility; all 21 optimizer
cases were rerun and pass. The other 49 passing cases were not rerun.

TypeScript, ESLint of the two changed TypeScript files, production build
and diff checks pass. Existing build chunk-size/Babel timing notices remain.
These are jsdom/type/build checks; no manual browser or physical-device
matrix is claimed. Backend code is unchanged: parent verification of 1,355
capture cases, strict Pyright/boot and five actual CPU VLM cases is inherited.
The release tag/assets and released changelog entries remain unchanged.

Logs: `/workspace/scratch/optimizer-save-{before,tests,tests-final,tsc,eslint,build}.log`.
