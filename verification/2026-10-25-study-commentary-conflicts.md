# Study commentary write/remove conflicts — 2026-10-25

While a model wrote a study commentary, another request could clear it or finish
a replacement first. The original response then restored the cleared content or
overwrote the newer result. A corrected baseline fixture reproduced 25 failures
and 5 passes in 3.62s across experiments, concepts, shelves, conjoint and scripts.

A per-study external file lock now covers commentary generation, replacement and
removal. Competing changes receive 409 before reaching the model. Existing text
survives rejected changes; provider failures release the lock for manual retry.
The project tree is still held only during input and commit, so users can delete
the study/project while a model is working. Final existence checks prevent late
responses from recreating deleted folders. Locks live outside the project tree.
Removing commentary from a missing study now returns 404 consistently.

Validation: 63 focused tests passed in 6.25s (all five study kinds, prior/no prior
text, concurrent rewrite/clear, failure/retry, and project/study deletion during
input/provider/commit). Existing rule A/B report and narrative flow also passed
in 3.88s: 64 tests total. Full backend Pyright: 0 errors, 0 warnings; boot passed.
No external inference was used.
