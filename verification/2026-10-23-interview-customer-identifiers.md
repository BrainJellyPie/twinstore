# Keep accepted customer IDs usable in journeys and interviews

Customer input and simulation accept arbitrary nonblank unique IDs, but journey and interview lookup
required a short ASCII filename. Korean IDs, spaces and 80-character IDs extended by scenario/town
cloning all failed with HTTP 400 after a successful run.

Journey lookup now treats the customer ID as an in-memory key. Transcript storage retains the existing
path for legacy filename-safe IDs and hashes other exact IDs into `interviews/by-id/`. The separate
directory avoids collisions with a customer whose literal ID equals a digest. Project/run/rack path
checks stay in place; customer IDs are neither normalized nor renamed.

Focused evidence:

- 17 API cases: Korean, Chinese, composed/decomposed accents, emoji, spaces, punctuation, lengths
  80/81/512, long scenario/town clones and literal numeric/null-like IDs. Each checks journey, empty
  transcript, fake-model answer, persisted reload and clearing.
- Four application-level cases with path separators/traversal-shaped IDs verify containment; one
  legacy/collision case verifies old transcripts and independent exact IDs.
- Before the fix: **19 failed, 3 passed in 6.14s**.
- New cases plus existing interview, concurrency, suggestion-race and project path checks:
  **47 passed in 12.27s**. Strict Pyright on the changed module: **0 errors**.

The existing HTTP path-segment routing is unchanged: slash-containing IDs are covered for safe storage
at the application layer, not claimed as newly supported HTTP URLs. Legacy ASCII transcript naming and
its filesystem case behavior are unchanged. No existing files are migrated or renamed.
No live model requests, full suite, frontend or release binary changes.
