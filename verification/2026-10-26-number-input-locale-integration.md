# Integrate current number-entry, locale and touch fixes

Integrated `claude/online-shopping-features-ji7y0f` through
`0c98cf10e1419fa75e0cea29b3363d4a6a0c5226` onto main `959cda0c`.
The incoming commits preserve a shelf panel when a dialog consumes Escape,
let bounded integer fields be emptied and retyped, localize decimal and
percentage displays, expose previously hover-only delete controls on touch
screens and focus the online click heatmap when its section link is used.
The upstream merge of main is retained as ancestry; already published
backend work is not applied twice. The only textual merge conflict was the
Unreleased changelog, resolved by retaining both entries. Released sections
are byte-for-byte unchanged.

Review found a state synchronization bug in the new `WholeNumberInput`:
after typing `40`, an empty string or out-of-range `500`, replacing its
controlled value with `12` left the old text displayed. Leaving the field
could then send the stale number back to the parent. Three new tests fail
on the incoming implementation; its three original tests pass.

The field now associates draft text with the numeric value it belongs to.
An external replacement clears that text, while an accepted manual edit
keeps its spelling and incomplete/out-of-range edits still wait for blur.
The regressions verify the displayed replacement, the blur callback and a
later return to the previous value without reviving the discarded text.

Verification passes 152 frontend tests across 13 focused files in 16.06
seconds. Coverage includes the input, money formatting, shelf-panel Escape,
online run/designer/report flows, optional heatmap focus, optimizer settings
and goal ownership, scenarios and the just-published additional-discount
editor. TypeScript and lint of all 50 changed TypeScript files pass with no
diagnostics; the production build passes with the existing Babel/chunk-size
notices. These are jsdom, static-code and compilation checks, not a physical
touch-device or browser matrix.

Backend files are unchanged from `959cda0c`. Its 543 focused backend checks,
zero-error strict Pyright result, boot smoke and 14 actual CPU model calls
remain the applicable evidence; they were not rerun for this frontend merge.
The published v0.8.2 assets remain unchanged.

Logs under `/workspace/scratch/`:

- `number-input-external-before.log`: three failing new cases, three passing old cases.
- `number-locale-integration-tests.log`: 152 passing cases.
- `number-locale-integration-{tsc,eslint,build}.log`: integration checks.
