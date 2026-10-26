# Area feedback, integer inputs and complete generated names

Integrated `claude/online-shopping-features-ji7y0f` through `98a5ce8a`
onto main `de547c46` (application baseline `d9829e63`). Incoming work preserves complete Unicode codepoints
when shortening generated layout, floor, experiment, store and ad names or
notes. Area/situation toggles expose their selected state; area day choices
and crowding options use separate, capitalized labels where appropriate.
Neighbor-analysis results receive focus when mounted and analysis errors
appear beside the Analyze button. Rival counts are integers bounded to
0–60, with blank retaining automatic estimation; seeds are whole numbers.

Only CHANGELOG.md conflicted. Both Unreleased sections are retained,
including main's automatic assortment price and shelf-purpose repairs.
Backend application/test code is byte-identical to the parent. No further
application repair was needed during this integration.

Verification passes 306 frontend cases across 12 affected/adjacent files in
19.72 seconds, covering generated Unicode names, scenario/town controls,
analysis context changes and stale responses, layout/building flows,
online experiments and discount previews. TypeScript reports no errors;
ESLint of all 17 changed TypeScript files reports no errors and one existing
React Compiler warning in AddLayoutDialog. Production build passes in
20.57 seconds with its existing Babel timing notice. Diff checks pass.
These are jsdom/type/build checks, not manual browser/device coverage.

The unchanged backend inherits 1,213 focused starter cases, strict
Pyright/boot and nine actual CPU model checks from the prior change.
Released changelog text and v0.8.2 tag/assets remain unchanged.
Logs: `/workspace/scratch/area-unicode-{tests,tsc,eslint,build}.log`.

Main advanced during publication with technical-report-only commit
`de547c46`. Its PDF, HTML, figure and report baseline are preserved.
Application code remains byte-identical to the tested integration.
