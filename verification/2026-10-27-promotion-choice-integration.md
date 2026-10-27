# Integrate promotion and capture-tab choice state

Merge `claude/online-shopping-features-ji7y0f` through
`7c21c750ef487abaa7e838b6cabe6a33ed6a8697`. Promotion-sign buttons in Shelf
Lab, shelf tests and the A/B builder, plus the Planogram/Shelf Lab switch,
expose their existing selection through `aria-pressed`. Selection handlers,
drafts, API payloads and persisted data are unchanged. All main fixes,
including generated product and shelf target validation, remain intact.

The merged tree passes **10 UI tests across four files in 7.02 seconds**,
including unsaved capture edits across tab switches. TypeScript has zero
errors; changed-file ESLint has zero errors or warnings. The production build
passes in 20.31 seconds with existing chunk-size/plugin-timing advisories.
Diff checks pass and the released 0.8.2 changelog section is unchanged.
Backend checks inherit fix 433's 535 passes and strict Pyright; no model-call
code changes. Logs, timings and test paths use
`/workspace/scratch/promotion-choice-*`.
