# Online demo branch integration — 2026-10-25

Merged 2f07bee1a6a20053e3533f084ba4a223b074b717 from the online features
branch. This adds README demos and screenshots and keeps comparison-player
headings on one line. Existing main fixes are retained.

Validation: 9 related frontend tests passed in 4.13s; TypeScript and changed-file
ESLint passed; production build passed in 18.89s with the existing chunk-size and
plugin-timing warnings. No backend code changed. Media objects are reused from
the already-published branch and the published merge tree is checked exactly.
