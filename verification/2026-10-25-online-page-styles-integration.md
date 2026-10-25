# Latest online page styles integration

Merged `a8586325aea737d7ab8eaafe56ebd42859904585` from
`claude/online-shopping-features-ji7y0f` into the main line after local starter fix
`8c55cf5d37819056414e2bab02d43c57e709eba1`. Only the changelog conflicted;
both entries were retained. The starter CPU harness and short product-code fix remain.

The branch introduces eleven page styles, style previews, per-template defaults
and two style experiments. Preview overrides use a copied site and do not save a
style implicitly. The picker remains inside the existing disabled editor fieldset
while writes/refetches are pending. Existing sites default to classic when the new
field is absent. Page snapshots carry the selected style into rendering/replay.

Validation on the merged tree:

- 67 backend tests passed: every style's desktop/mobile crawl and control bounds,
  deterministic rendering, non-mutating style preview, invalid style rejection,
  replay vision transforms and the core online store cases.
- 118 frontend tests passed across the online feature and persona-label mapping
  suites, including designer persistence, write locks, identity changes and experiments.
- Full source Pyright: zero errors/warnings. Backend server import passed.
- TypeScript build, changed-file ESLint (10 files), and Vite production build passed.
  Vite retained the existing large-chunk/plugin-time warnings.

The backend test run took 126.99 seconds while the actual CPU model and other
integration checks shared the five available CPU cores. It is not a performance
measurement. Subsequent model timing comparisons should run without concurrent
build/test workloads. No full repository test suite was run.
