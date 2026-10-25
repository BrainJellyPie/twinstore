# Allow normal text in a store that defaults to large print

The built-in Senior Care store offered “Use normal text,” but clicking it left
large print enabled: rendering OR-ed the visitor's preference with the store's
default. Repeated model decisions could therefore keep choosing an ineffective
action.

Browser state now records whether the visitor has changed text size. An explicit
choice overrides the store default and survives serialized requests, navigation
and Back. Older saved states without that flag retain their previous appearance;
a new visit still starts with the store's default. The frontend state type accepts
the flag optionally for older responses.

Before repair: **7 regressions failed, 4 controls passed**. After repair,
**66 distinct focused backend checks passed**: 55 existing browser/overlay
controls and 11 targeted text-size/API cases (the latter completed in 4.26 seconds).
The targeted tests cover both defaults, both devices, repeated toggles, JSON
round trips, older snapshots, a scripted model choice, and real browse requests.
An initial test incorrectly expected clickable settings text in the outline;
it was corrected to inspect the rendered panel and corresponding API option.
Full-source Pyright, backend boot, frontend TypeScript and changed-file ESLint
passed without diagnostics. No frontend runtime behavior changed, so its build
and runtime tests were not repeated. No live inference was used.
