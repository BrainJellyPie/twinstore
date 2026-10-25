# Distinguish a missing grounding answer from an empty shelf

The shelf-grounding schema defaulted `products` to an empty list. Replies such
as `{}` or `{"boxes": [...]}` therefore passed validation and were cached as
`{"products": []}`. Capture skipped its correction attempt and used classic
image detection on every repeat, even though the model had not explicitly
reported an empty shelf.

Require `products` in the private model response and state that requirement in
the prompt. An explicit `products: []` is still valid. Omitted lists now use
the existing two-attempt validation path, and persistent failure keeps the
existing classic-detector fallback. Schema changes separate old cache entries;
coordinate parsing, the 80-box cap, output budget and cropped-label limits are
unchanged.

Fourteen real LiteLLM/Instructor HTTP capture cases cover both structured modes,
missing and misnamed lists, correction, persistent failure, a later retry,
old-schema cache entries and explicit empty lists. They run the actual capture
pipeline on a small drawn shelf, including box refinement and classic fallback.
Successful correction retains all three model boxes and uses the valid cache
on repeat. A schema check verifies that products is required while [] is valid.

Before the fix, 13 tests failed and two passed in 2.77 seconds. The focused
required-list, unused-label, output-budget and capture suite passed 99 tests in
9.43 seconds. One native Grounding DINO test was skipped. Full source Pyright
reported zero errors and warnings. The 42 warnings were existing LiteLLM async
logging cleanup warnings. No native inference, model downloads or paid requests
ran; the HTTP answers are scripted, not a test of real-model visual accuracy.
