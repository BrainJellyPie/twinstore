# Integrate the expanded online-store branch

Integrated `claude/online-shopping-features-ji7y0f` at
`eb09e59e3550592c8d9f93dcab462612c23f0896` into main after
`6ec15a98cc60605c711679b1ff0504f2bcb34454`.

The branch adds eyesight-aware shoppers and screenshots, friction reports,
exit surveys, ad campaigns with comparison reports, and quick design experiments.
It also includes preparation notes for v0.5.0. The published v0.4.14 tag and
release branch remain unchanged; this integration does not publish v0.5.0.

The launcher conflict was resolved to retain both quick experiment creation and
main's explicit model-choice validation. Model-list and experiment variables
are separate, and session estimates include the selected experiments. The new
store-options fetch is mocked in the model-selection tests to keep them offline.
The text-size override, endpoint device mix, preview transitions, cart/wishlist
paging, overlay sizing and other previous main fixes remain present.

On the merged tree:

- **361 online backend tests passed in 48.58 seconds**, covering every online
  engine and API test, including the newly integrated ads and existing local SDK
  truncation cases. Fifteen existing LiteLLM asynchronous logging warnings remain.
- Full-source Pyright: zero errors and warnings; backend boot: passed.
- **114 frontend tests passed in 9.55 seconds**, covering online components,
  experiments, shared physical-store model selection and six-language catalog
  consistency.
- TypeScript and changed-surface ESLint: passed without diagnostics.
- Production build: passed in 18.14 seconds, with existing bundle-size/plugin
  timing warnings.

No live model calls, model downloads, full local backend suite or release
workflow were run for this integration. The upstream full-suite and browser
claims remain scoped to the commits documented in its release-preparation note.
