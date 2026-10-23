# Product variants use a current, coherent source

Product edits and starter fills checked their source digest while preparing a child layout.
The final tree guard only checked parent existence. A concurrent floor save could finish
between preparation and persistence, yet the old preview still saved successfully. A source
operations save already holding its layout lock could also finish after a child had read
the old settings, leaving the child without the new stock/backroom configuration.

Final persistence now takes the tree guard followed by the source layout lock, matching
the established project/layout lock order. It rechecks the store/catalog digest and currency,
then copies current operating/building settings and writes the receipt and child while holding
those locks. Preparation remains outside the critical section. Existing accepted-request
replays still return their prior child without overwriting subsequent edits.

- Baseline: 6 failed, 2 passed in 3.88 seconds.
- After: 142 passed in 15.82 seconds across the source-race cases and both feature API suites.
- Cases cover both child types, floor changes versus operating settings, an editor already
  holding the source lock, and an edit after child preparation. Stale previews leave neither
  a child nor a receipt; operating updates survive in the child and retries remain idempotent.
- The existing pre-commit deletion test now injects deletion after draft preparation, before
  the protected source read, so it still exercises the intended deletion-before-commit order.
- Strict Pyright for both changed application modules: zero errors/warnings.
- No live model calls, frontend changes or full suite.
