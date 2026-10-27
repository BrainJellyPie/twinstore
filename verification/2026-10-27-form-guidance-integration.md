# Integrate review requirements and neighborhood size wording

Merge `claude/online-shopping-features-ji7y0f` through
`3c321fcca117130a4f93d4ba2a053d5136c96184`: the two new commits are `4be01385`
and `3c321fcc`. Preserve all published main changes, including the rupee/real
conversion fix and shopper-clock diagnostics. Retain both changelog additions
and the released 0.8.2 section unchanged.

The price-check review button explains its required store reference, audit
date and two CSV files while unavailable; an accessible description connects
the button to that text. The neighborhood summary identifies size as the
area's side length, so a 600-m import radius no longer appears to be a 1,200-m
radius. Both additions use the six-language catalog and existing localized
number formatting. Validation rules, API payloads and stored sizes are unchanged.

The merged tree passes **76 UI tests across three files in 4.20 seconds**:
price checks, the neighborhood page and i18n. TypeScript has zero errors and
changed-file ESLint has zero errors or warnings. The production build succeeds
with the existing bundle advisories; exact duration is recorded in the build
log. Diff checks pass. No backend or model-call code changes, so prior fix
427 and integration 428 checks are inherited without another backend run.
Logs, command timings and test-file paths use
`/workspace/scratch/form-guidance-*`.
