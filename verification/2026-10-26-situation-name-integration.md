# Run-summary situation names

Integrated `claude/online-shopping-features-ji7y0f` through `38f0bb1c`
onto main `3ee637c8`. The run summary translates the built-in ordinary-day
and unnamed custom situation in the selected language. User-entered names
remain unchanged. All six language entries are present. Both Unreleased
changelog histories are retained; the v0.8.2 notes and release are unchanged.

The five affected/adjacent run-launcher and scenario-editor test files pass
117 tests in 10.14 seconds. TypeScript and lint of the three changed
TypeScript files complete without errors or warnings. Production build
passes in 20.58 seconds with existing chunk-size and Babel-timing notices.
Diff checks pass. No additional application change was needed.

Backend code is unchanged: the preceding 1,837 focused capture tests,
strict Pyright, boot check and six final CPU VLM trials are inherited,
not rerun. No new CPU inference or manual browser coverage is claimed.

Logs: `/workspace/scratch/situation-name-{tests,tsc,eslint,build}.log`.
