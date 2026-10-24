# Preserve shelf-test edits without optional fields

A complete shelf-test price, package or sign change could fail because the local
model wrote null for unused package/promo text, rationale or age restrictions.
Normalize only those optional fields to their existing empty defaults and state
the convention in the prompt. Required names and product targets, nonnull type
checks, text bounds and allowed age labels remain strict.

Before the fix, eight cases failed and 19 controls passed in 3.10 seconds.
Scripted HTTP covers both JSON modes, each independent edit kind, omitted
restrictions, explicit age restrictions and explanations, exact SKU/rack,
price/package/sign effects, unchanged source data and cached repeats. A draft
with no operation still returns the existing review warning and leaves the
layout unchanged; no new edit is invented.

After the fix, 110 focused shelf-test and API checks passed in 3.74 seconds.
Full source Pyright reported zero errors and warnings. The 24 pytest warnings
are existing LiteLLM async logging cleanup warnings. No native model inference
was used.
