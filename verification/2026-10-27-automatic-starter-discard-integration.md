# Preserve automatic starter work while integrating dialog and search changes

Merge `claude/online-shopping-features-ji7y0f` at
`4a75de5e3d9c61f1289e30aaa4b4268c89d1270e`: five new commits add discard
confirmation to starter filling and bulk product editing, describe area-map
tools, and remove empty search sections. Keep both Unreleased changelog entries
and the receipt subtotal evidence fix already on main.

The incoming starter confirmation only considered typed requirements or
manually selected shelves. Automatic generation with empty requirements could
therefore be dismissed without confirmation, losing either its pending result
or a completed preview. Pending model/preview requests and the prepared draft
now count as unsaved work. Keeping the dialog open continues the existing
request; explicitly discarding it still ignores late results. A save already
in progress retains the existing close behavior.

The new search also treated a failed run-list request as an empty result.
Only successful queries can now establish an empty run list, and pending/error
states remain visible. Existing localized loading text and original server
diagnostics are reused; no new translation keys are needed.

Three new reproductions fail before the fixes (32 other tests pass, 8.24s).
After the changes, six affected suites pass 86 tests in 11.06s, including
cancelled close, confirmed discard, empty requirements, completed previews,
late responses, saves and failed searches. TypeScript and ESLint pass without
diagnostics; Vite builds in 20.98s with existing chunk/plugin warnings.
These are DOM checks, not a real-browser smoke or model inference.
Backend validation is inherited from fix 456: 368 targeted tests, strict
Pyright, server import and eight actual CPU receipt cases. Backend source
is unchanged here. Release v0.8.2 and older changelog bytes are preserved.
Logs use `/workspace/scratch/ui-auto-discard-`.
