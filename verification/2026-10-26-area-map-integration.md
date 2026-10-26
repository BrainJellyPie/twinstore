# Narrow-screen Area map integration

Integrated `claude/online-shopping-features-ji7y0f` through `a6d71c11`
onto main `39e3bbc0`. The map legend flows below the map on narrow screens;
the desktop overlay is preserved. Loading and error states retain their
map-sized panel. Only the Unreleased changelog conflicted; both entries
are retained. Released notes and v0.8.2 tag/assets are unchanged.

The three Area test files pass 78 cases in 6.07 seconds, covering loading,
recovery, draft ownership, selected controls and stale analysis results.
TypeScript and ESLint of the changed component report no errors or
warnings. Production build passes in 20.58 seconds, with existing large
chunk and Babel timing notices. These checks do not establish rendered
phone/device geometry; no manual browser/device check is claimed.

The accompanying unavailable-price CPU diagnostic is described in
`2026-10-26-starter-unavailable-cpu.md`. None of its unsuccessful production
candidates is retained. Backend application/test code is byte-identical
to the parent and inherits its 1,213 focused cases, strict Pyright and boot
checks. The diagnostic compiles; replaying its original failed response
uses zero HTTP requests and correctly remains a failure.

Logs: `/workspace/scratch/area-map-{tests,tsc,eslint,build}.log` and
`/workspace/scratch/starter-unavailable-*.log`.
