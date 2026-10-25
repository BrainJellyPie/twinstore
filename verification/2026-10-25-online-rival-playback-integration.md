# Independent rival visits and playback startup — 2026-10-25

Integrated online-shopping branch 2adcd5ad (feature commit acaf1e1e). Rival visits
now draw from a separate deterministic stream instead of replaying the abandoned
visit at an identical shop. Compared variants retain their common random numbers.
Playback shows the loaded page before click metadata arrives; animation still
waits for that metadata. Metadata rendering skips eyesight filters, which alter
pixels but preserve screenshot dimensions and hit boxes. Actual images and GIFs
retain those filters. The changelog conflict was resolved by retaining both the
free-price fix and the branch entries.

Validation on the merged tree: 37 backend cases passed in 21.99s, including
rival outcomes and identity, accepted image snapshots and GIF export. Seven
JourneyPlayer/SideBySide cases passed in 3.31s. Full backend Pyright reported
0 errors and 0 warnings; server boot passed. Frontend TypeScript and changed-file
ESLint passed; production build passed in 18.51s with existing chunk-size and
plugin timing warnings. No live model calls.
