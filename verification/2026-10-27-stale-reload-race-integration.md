# Integrate recovery and selection controls; prevent duplicate reloads

Merge `claude/online-shopping-features-ji7y0f` at
`85b3b7ea322050192330dd09bee326c145f054ef`. Three new commits check backend
availability before reloading a missing frontend chunk, add arrow-key/focus
behavior to online style and shopper-policy radio groups, and distinguish no
promotion from mixed promotions in the bulk editor. All six languages have
the new guidance. Both sides of the Unreleased changelog conflict are retained.

The new asynchronous health check creates a race: the preload handler and
route-error handler can both pass the initial reload guard, await health,
and then both reload. Two deferred-promise tests reproduce it with either
request finishing first. Both fail on the incoming branch (1.62 seconds).
The reload guard is now checked again after health succeeds, before writing
the timestamp and reloading. The later continuation returns `show` instead
of triggering a second reload. Offline and blocked-storage behavior remain.

Seven affected test files pass 53 tests in 7.00 seconds. The route test emits
jsdom's navigation-not-implemented diagnostic; the race tests use an injected
reload callback and verify exactly one call. These are DOM/unit checks, not
an actual browser navigation smoke. TypeScript and changed-file ESLint pass
with no errors or warnings. Vite builds in 21.59 seconds with existing chunk
and plugin timing warnings. Diff checks pass. Backend validation is inherited
from integration 454 (318 receipt tests, strict Pyright, server import), since
no backend source changes here. The v0.8.2 notes and all older changelog text
are byte-identical; no release tags or assets change.
Logs use `/workspace/scratch/ui-stale-reload-race-`.
