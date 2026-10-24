# Preserve storefront measurements when the explanation is absent

A complete set of valid storefront scores was rejected when the local model
returned null for the optional reasons field. The storefront API then returned
502 and could not save the measured venue attractiveness.

Normalize only a null explanation to the existing empty-string default and
state that convention in the prompt. Preserve all five required 0–10 scores,
nonnull text validation, the explanation length bound and failure behavior.

Before the fix, eight cases failed and 59 controls passed in 5.33 seconds.
Scripted HTTP covers both JSON modes, minimum/neutral/maximum scores, null,
empty and omitted explanations, correct attractiveness and cache reuse. API
cases verify persisted attraction changes only for the selected venue. Missing
or invalid measurements and malformed text remain rejected.

After the fix, 71 focused vision-input and API checks passed in 4.70 seconds.
Pyright reported zero errors and warnings. The 17 pytest warnings are existing
LiteLLM async logging cleanup warnings. No native model inference was used.
