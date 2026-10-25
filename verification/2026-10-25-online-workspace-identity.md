# Online workspace resource state — 2026-10-25

Switching stores while the simulation tab was open retained the previous
RunLauncher state: the header showed B but Start run submitted A. Switching
between already-cached reports retained the previous shopper, variant and open
journey, requesting a new run with old identifiers (including a nonexistent
variant). Resource keys now remount the launcher/report when their store/run
changes. Selecting a tab also pins the current store, so refreshing/reordering
the store list during copy creation does not reset the active form.

Baseline: all three UI regressions failed in 5.62s, including the actual start
request and replay arguments. Final verification covered 44 distinct cases:
43 passed in the combined run; the new list-reorder test initially used an
incorrect label, which was corrected, and all four workspace cases then passed
in 4.55s. Existing launcher model/experiment retry and report tests passed.
Frontend TypeScript and changed-file ESLint passed; production build passed in
18.33s with existing chunk-size/plugin timing warnings. No backend source
changed or live model calls were made.
