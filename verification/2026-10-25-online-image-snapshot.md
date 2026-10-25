# Online run artwork snapshots — 2026-10-25

Online runs froze site JSON but loaded mutable project artwork. Replacing a SKU
image or deleting a package after acceptance changed queued/running input; later
image uploads also changed historical replay. Seven image-integrity cases failed
against the previous implementation (four worker cases, three replay cases).

Each new run now freezes resolved art, including absent art, under the existing
project and image guards. This includes all compared sites and the rival. Workers,
PNG replay (plain and highlighted), playback metadata and GIF export use the same
snapshot. A failed copy removes the pending folder before submission. A missing
snapshot manifest returns an error instead of reverting to live images. Legacy
runs without the marker retain their previous replay behavior; their original
artwork cannot be reconstructed retroactively.

Validation:
- 27 focused tests passed in 34.49s: new image boundaries, online API, rival API,
  lifecycle, playback and GIF endpoints.
- Extended replay coverage to the rival as well as both variants: all 13 snapshot
  tests passed in 9.41s. Cases cover SKU replacement, added artwork, deleted
  packages, queued/running mutation, copy failure, lost manifest/folder and legacy
  runs. Worker probes use the real rule simulation; no model service was called.
- Full backend source Pyright: 0 errors, 0 warnings. Server boot passed.
