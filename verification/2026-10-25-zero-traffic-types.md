# Keep empty hours from invalidating customer generation

A model-written hourly estimate with zero visitors and null person_types was
rejected alongside the day's otherwise valid positive hours. After bounded
retries, that one unused label list prevented the whole population from being
generated.

Normalize null person_types to an empty list only after visitor_count has
validated as exactly zero. Reinforce the empty-array convention in the prompt.
Positive counts still require valid lists, and malformed counts or nonnull
label structures remain invalid. The existing all-zero-day fallback is unchanged.

Before the fix, 12 cases failed and 10 strict controls passed in 3.71 seconds.
Scripted HTTP covers JSON and JSON-schema modes, positional and legacy explicit
hours, midnight/daytime/closing boundaries, Monday and Sunday, unique customer
IDs, exact visit hours, preserved traffic estimates and normalized cache reuse.
Three actual visitors per day remain three; no generic-day fallback or twins
are introduced for the mixed zero/positive estimates.

After the fix, 164 focused traffic and customer-generation checks passed in
4.94 seconds. Full source Pyright reported zero errors and warnings. No native
model inference was used.
