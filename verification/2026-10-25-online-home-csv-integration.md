# Online home access and rival CSV context — 2026-10-25

Integrated online-shopping branch 41efa693 (feature a47a9b8c): home and store-card
links reach online stores, the home badge reads v0.5, and exported rival visits
use their actual search-engine arrival instead of the shopper's original source.
All clickstream call sites use per-store visitor context. Both sides of the
changelog conflict were retained.

During review, guarded the home action while the initial store list is loading
or has failed without a usable store: these states must not be mistaken for a
confirmed empty account and send the user into store creation. Added the two
loading/error assertions. Renamed the new route test with TanStack's ignored
prefix so it is not scanned as a page.

Validation: 37 backend cases passed in 27.10s (online store, reminder and rival
API behavior). Fourteen frontend cases passed in 2.93s (home routing, store
cards, catalog ownership); after the test-file rename its four routing cases
passed again in 2.32s without the route-file warning. Backend Pyright: 0 errors,
0 warnings; server boot passed. Frontend TypeScript passed; lint had no errors
and two existing-style Fast Refresh warnings in index.tsx. Production build
passed in 17.67s with chunk-size/plugin timing warnings. No live inference.
