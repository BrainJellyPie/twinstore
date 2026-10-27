# Inventory localization and pattern-bound test integration

Merged `claude/online-shopping-features-ji7y0f` at
`0398e8196a1c91b9cf112d9e219809bffb461abd` onto main
`ecd5254940f068114092da905d12fded393543af`.

Inventory review now formats its maximum-day count consistently in the rules
and disabled-button explanation. Field-pilot timing limits use consistent
digit grouping. Existing numeric validation limits are unchanged.

The incoming pattern test correctly measures bounded echoed model text rather
than the size of the whole stage-two prompt, which also includes the JSON
response schema. Before integration the JSON case failed the unrelated total
length cap (1 failed, 36 passed in 3.24 seconds). The corrected assertion still
checks removal of the oversized grammar and the 600-character reasoning bound.
All 37 cases pass in 3.34 seconds.

Frontend verification: 64 tests in four inventory/timing/i18n suites pass in
4.31 seconds. TypeScript, changed-file ESLint and the production build pass.
Backend application source is unchanged; strict Pyright and server boot are
inherited from main 464, along with its 456 focused survey tests.

During publication, main independently advanced to
`0799ae0384d0674cff1ec42ffcdf8f6c81d06b68` through release PR #8. That merge
already includes these code/test changes and places the concept-draft fix in
its v0.9.1 changelog section. Its exact changelog is retained; only this
verification report remains to be published. The application tree is unchanged
from that main commit. This task creates no release/tag and changes no published
release assets. Existing v0.8.2 changelog text is byte-identical.
