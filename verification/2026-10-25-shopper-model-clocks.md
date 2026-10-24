# Keep malformed model times from widening customer searches

The natural-language shopper finder accepted arbitrary clock strings from the
model. The downstream filter warned and omitted an invalid time, so a request
for customers after a certain hour could return everyone instead. That invalid
model response was also reusable from the cache.

Validate nonempty arrival clocks in the model response used by find_shoppers.
An invalid clock enters the existing bounded structured-response correction
loop before matching or caching. Clarify 24-hour notation in the prompt.
Keep the lower-level filter's legacy warning behavior, ordinary missing-time
defaults, optional seconds, day endpoints and inclusive-after/exclusive-before
comparisons.

Before the fix, 48 scripted-HTTP cases failed and 16 valid-clock controls passed
in 3.71 seconds. Both JSON modes cover malformed hours, minutes and suffixes,
AM/PM text, invalid end-of-day times, each bound, correction, repeated failure,
later recovery and cached reuse. They verify the actual returned customer IDs
on both sides of a boundary rather than only response parsing.

After the fix, 237 focused model, filter-boundary and search API checks passed
in 5.25 seconds. Pyright reported zero errors and warnings. No native model
inference or model download was used.
