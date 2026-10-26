# Layout rename integration and pending-edit protection

Integrated `claude/online-shopping-features-ji7y0f` through `14bd0504`
onto main `0ce64416`. Layouts can be renamed in Store & layout, with
six-language labels. The API trims names and rejects blank or over-300-character
names; finalized layouts retain existing server protection.

Review found two pending-save bugs in the incoming component: changing the
input reset the mutation's pending state and allowed overlapping saves, and
an earlier acknowledgement erased a newer draft. Two regression cases fail
against the incoming component (three original cases pass). The integration
keeps the save guard until settlement, clears only the acknowledged draft,
and shows Saved only for the current saved name. The input/button retain
focus while waiting. Parent component identity includes both project and
layout, keeping old pending callbacks separate from a newly selected project.

The final rename file has seven passing cases, adding rapid double-submit
and corrected retry after failure. All 83 cases across seven adjacent UI
files pass in 6.82 seconds. All 37 cases across five backend files pass in
9.35 seconds, covering name validation, creation, lock isolation and save/run
races. Strict backend Pyright reports zero errors/warnings and boot passes.
An initial Pyright invocation from the repository root omitted the backend
configuration and failed dependency resolution; it was corrected to the
backend working directory. That invocation is not counted as a code failure
or a successful check.

TypeScript and lint of all four changed TypeScript files pass with no
errors/warnings. Production build passes in 20.66 seconds with the existing
chunk-size and Babel-timing notices. Compilation and diff checks pass.

The separate online-goal-status report documents the diagnostic change,
four offline CLI audits and two new actual CPU visits, including remaining
model narrative errors. Package reading is unchanged and inherits 411's
236 package tests and six passing CPU probes. No full suite or manual
browser/device coverage is claimed. The changelog retains both histories;
released notes and v0.8.2 remain unchanged.

Logs: `/workspace/scratch/layout-rename-{before,frontend-tests,backend-tests,pyright,boot,tsc,eslint,build}.log`.
