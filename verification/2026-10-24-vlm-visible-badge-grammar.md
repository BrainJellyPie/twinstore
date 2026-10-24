# Restrict local vision grammars to visible badge numbers

Shelf glances previously used an integer range of 0 through 10,000 for every
image. A grammar-constrained local model could therefore emit a structurally
valid badge that did not exist on the shelf. Untagged-photo comparisons used the
same grammar even though their prompt asked for number zero. Existing resolution
guards rejected unusable choices after generation, but the grammar could prevent
these choices earlier.

The request-local ShelfGlance subclass now adds an enum containing zero and the
actual marks in the current view, including sparse sets and empty shelves. Single
models, mixture routing, vote ensembles and larger-budget truncation retries use
that schema. Sim2real render/tagged-photo conditions use their own view's marks;
raw photos allow only zero. Stable ShelfGlance values leave the single-model
boundary so cached and fresh answers compare consistently.

The enum constrains supporting providers; it does not replace runtime name
resolution. A provider ignoring JSON grammar can still identify a valid printed
name despite a wrong badge. Existing raw-photo number suppression, invalid-choice
handling, no-pick behavior, interest limits and model-call retry bounds remain.
This patch does not claim that a model will always associate a valid badge with
the correct picture.

Eighteen HTTP schema-contract regressions failed before implementation. Final
focused verification passed 143 tests in 33.53 seconds, with zero strict Pyright
errors. Coverage includes dense/sparse/empty marks, single/mixture/vote routing,
cache reuse, actual truncation recovery, non-enforcing providers, conflicting
names and numbers, raw-photo invalid numeric choices, complete vision shopping
and rendered/photo comparison paths. Nine existing LiteLLM logging-cleanup
warnings occurred. All responses and transports were scripted; no live or paid
inference was used.
