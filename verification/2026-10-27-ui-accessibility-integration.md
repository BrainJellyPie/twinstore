# Integrate current UI feedback and selection changes

Merge `claude/online-shopping-features-ji7y0f` at
`f8d1aff0a3c755f703e68ce328e12654eb6c40e1` into current main. Five new
non-merge commits announce layout upload results and errors, announce
previously visual-only errors, show fixtures outside a resized floor
immediately, and expose the selected photo/field-pilot/protocol/revision
controls to assistive technology.

The only conflict is the Unreleased changelog; both branches' entries are
retained. The existing v0.8.2 changelog section and published assets are
unchanged. The branch's older backend merges introduce no additional
backend changes over main.

Validation: five affected frontend test files pass 67 tests in 6.32 seconds.
TypeScript compilation passes; Vite builds in 21.61 seconds. Changed-file
ESLint reports zero errors and one existing fast-refresh export warning in
`LegacyDetectModal.tsx`. Vite retains chunk-size/plugin-timing warnings.
Diff checks pass. Backend validation is inherited from immediately preceding
integration 444 (756 tests, strict Pyright and server import); it was not
rerun for these frontend-only changes.

Logs use `/workspace/scratch/ui-accessibility-merge-`. This integration does
not validate local-model shopping semantics; that investigation continues
from the duplicate impulse purchase recorded in the operation-schema report.
