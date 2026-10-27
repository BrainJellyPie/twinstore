# Integrate localized price entry

Merge `claude/online-shopping-features-ji7y0f` through
`8a337ebe912b70caa4c5163754c9a92393a58291`, including the three new changes
`87ada6a7`, `b18fc986` and `5f0550cd`. Preserve the published currency-tag
fix `2d699e5e` and every existing main change. Resolve only the changelog's
overlapping additions, retaining both sets of notes and the released 0.8.2
section byte-for-byte.

French and Spanish price fields accept a comma followed by one or two
decimal digits; existing three-digit thousands grouping remains unchanged.
Conjoint price lists in these locales split on semicolons or a comma followed
by whitespace, so `1,49, 2,79 ; 3,10` sends `[149, 279, 310]` minor units
instead of splitting each decimal number. Other locales retain their previous
parsing. Localized placeholders show the intended separators. The Spanish
online-store list uses the same run-count wording as its Runs section.

The merged tree passes **261 UI tests across ten files in 15.55 seconds**,
covering money conversion, conjoint submission, price round trips, marketing
price validation, capture currency/edit state, site editing, store lists and
i18n. TypeScript has no errors; changed-file ESLint has no errors or warnings.
The production build succeeds in 20.70 seconds, with existing chunk-size and
plugin-timing advisories. Diff checks pass.

No backend or model-call code changes in this integration. It inherits fix
427's 2,361 focused backend passes, strict Pyright, application import and
six fresh CPU currency cases; they were not rerun for UI copy/input changes.
Logs, command timings and the exact test-file list use
`/workspace/scratch/decimal-comma-*`.
