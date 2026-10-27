# Integrate choice-state accessibility and review guidance

Merge `claude/online-shopping-features-ji7y0f` through
`4717f5f3c197edf61eb251cfe6278f2a449bce1d`, including the four new commits
`a768a3ff`, `35894db8`, `918b172b` and `e1a5c69a`. Preserve all main changes,
especially fix 431's generated-product validation. Resolve the overlapping
changelog additions while retaining the expanded review note and the
released 0.8.2 section unchanged.

Choice buttons now expose their existing selected state through
`aria-pressed`: package pictures, capture/Shelf Lab choices, marketing chips,
discount/placement levels, optimization scope and judge, provider models,
shopper sort/group segments and Journey/Interview. Selection handlers and
stored values are unchanged. Unit-price and inventory review buttons have
six-language requirement text connected through `aria-describedby`, following
the existing price-check form. Validation and API payloads are unchanged.

The merged tree passes **158 UI tests across thirteen files in 14.41 seconds**.
TypeScript has zero errors and changed-file ESLint has zero errors or warnings.
The production build succeeds in 19.89 seconds with existing bundle-size and
plugin-timing advisories. Diff checks pass. Backend and model calls are
unchanged; fix 431's 513 backend passes, strict Pyright and documented CPU
limitations are inherited without rerunning them for accessibility attributes.
Logs, timings and the exact test-file list use
`/workspace/scratch/choice-state-*`.
