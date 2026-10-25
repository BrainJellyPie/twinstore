# Keep the online view alive while saving its address

Date: 2026-10-25. Integrates `90596d60969993e07233cde7bdddac787e9f55d8`
over main `01241167961d22921e6da71adb08c3b9e44e545a`.

The incoming branch adds online store/report addresses, missing-page recovery,
report section navigation, and phone/readability improvements. Its native
`history.replaceState` call is also observed by TanStack's browser history.
The route keyed the entire page by every search parameter, so saving the selected
store or consuming a comparison/replay hand-off remounted the page and discarded
its state. The first Design click returned to Browse, an incoming comparison lost
its target, and a linked customer replay lost its customer.

All three failures reproduced with the real browser-history router in jsdom.
The existing test mocked the router, hiding that notification/remount behavior.
The page now uses the resolved history entry's key. Saving its address retains
that entry and the current view; a routed link gets a new entry and opens its
incoming selection. Using the pending location instead was insufficient: its
new key could mount the page with the old route search, which then overwrote the
new address. The resolved location avoids that ordering race.

Checks cover the first Design click, comparison hand-off, customer replay,
navigation to a different report, and a replacement link to another comparison.
All 46 focused frontend tests passed, as did TypeScript and changed-file lint
(zero errors, four existing route fast-refresh warnings). The production build
passed in 20.28 seconds with the usual bundle/plugin warnings. No backend
application source changed in this integration.
