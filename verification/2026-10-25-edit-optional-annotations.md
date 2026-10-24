# Keep applicable edits without optional annotations

Valid automatic price and placement edits failed when the model returned null
for a layout summary or an A/B rationale or focus-product list. These fields
already supported omission, and the experiment converter already derived its
focus from the changed products when no focus was specified.

Normalize only those null annotations to their existing empty defaults and
make the conventions explicit in both prompts. Required edits and names,
malformed nonnull annotations, length bounds and applicability validation stay
unchanged. An explicit focus list remains authoritative.

Before the fix, eight cases failed and 18 controls passed in 3.33 seconds.
Scripted HTTP covers both JSON modes, layout and experiment drafts, null,
omitted and explicit Unicode annotations, and USD/KRW prices. Checks apply a
combined price change and shelf move, preserve the exact destination, level
and minor-unit price, check focus selection, reuse cache and leave the source
store unchanged. Independent null fields and malformed controls are covered.

After the fix, 183 focused engine and API checks passed in 8.17 seconds. Full
source Pyright reported zero errors and warnings. The 46 pytest warnings are
existing LiteLLM async logging cleanup warnings. No native model inference was
used.
