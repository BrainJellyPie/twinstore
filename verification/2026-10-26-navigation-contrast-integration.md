# Integrate page navigation focus and theme contrast

Merged the feature branch through `2f08f52a3417a0e3a660e253e697abf0bb54fdaf`
onto main `6e811759`. The incoming changes are `71ce7a7f` (compass/floor edit
contrast), `8cba0554` (gradient/status contrast) and `2f08f52a` (page focus and
skip link). The branch's intervening main merge adds no new backend work.

The root layout now exposes a six-language skip-to-content link and focuses
the page after navigation when focus has fallen onto the document body. It
waits briefly for an old page/palette to close and preserves focus acquired
by the new page. Its four router tests cover the skip link, removal of the
old focused control, delayed palette close and a new page's focused input.
Theme changes use dark foregrounds on bright dark-mode fills and stronger
light-mode gradient endpoints. Compass labels no longer use 45% opacity.

Validation: 106 frontend tests pass across nine relevant suites in 15.02
seconds, including root navigation, palette, error recovery, reports,
analyst, interviews, upload queue and product library. TypeScript and the
production build pass (21.01 seconds). Changed-file lint covers 20
TypeScript files with zero errors; the three route fast-refresh warnings
also occur when linting those files from the main parent. Build chunk-size
and Babel timing notices remain.

Static WCAG contrast calculations for the opaque gradient endpoints and
positive/negative/destructive fills pass 4.5:1 with the chosen foregrounds.
Light endpoints range from 4.576 to 5.084; dark endpoints from 7.027 to
12.454. These are color-token checks, not a rendered browser accessibility
audit or a claim about every animated overlay and transparent surface.
No new browser/operating-system matrix was run for this integration.

Only the changelog conflicted; both sets of Unreleased entries are retained.
The released changelog from v0.8.2 onward is byte-identical. Backend code is
unchanged from the preceding compact-schema fix, whose 410 focused tests,
strict Pyright and boot checks remain the backend evidence; they were not
repeated for this UI merge. The published v0.8.2 tag/assets are unchanged.

Logs: `/workspace/scratch/navigation-contrast-{tests,tsc,eslint,build}.log`,
`navigation-contrast-parent-eslint.log` and
`navigation-contrast-token-check.json`.
