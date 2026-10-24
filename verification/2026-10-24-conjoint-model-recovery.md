# Correct unusable automatic conjoint drafts before caching

The JSON response schema accepted drafts that could not become conjoint studies:
duplicate or blank levels could remove every attribute, prices could collapse
after currency rounding, and an empty product could fail the final request
model. These responses were cached before conversion raised an error. Repeating
the same draft request then retrieved the unusable response without inference.

The per-request response model now validates the normalized design against the
existing study rules inside Instructor's correction loop. It uses that request's
currency and product context. One correction is allowed, retaining the existing
two-attempt budget. Only usable drafts enter the response cache. The prompt now
states distinct usable axes, distinct prices after currency rounding, and finite
realistic amounts. Existing normalization and valid no-price studies remain
unchanged. The changed prompt and schema also separate previous cached drafts.

Nineteen malformed outputs are exercised with both immediate correction and
repeated failure followed by a later successful request (38 cases). They cover
blank products, price-only attributes, whitespace and case duplicates, levels
that collide after truncation, insufficient axes, one/repeated/rounded prices,
sub-minor amounts, nonfinite values and unsafe finite amounts in USD/KRW/JPY.
The tests use mocked HTTP through real OpenAI, LiteLLM and Instructor; they check
request counts, correction feedback, final study validation and cached content.
An additional concurrent USD/JPY test proves the same prices can be accepted in
cents while requiring correction in yen, with independent cache reuse.

Before: all 38 new failure cases reproduced. After: 75 focused recovery and
existing conversion checks passed in 2.93 seconds; the added currency-isolation
control also passed. Strict Pyright reported zero errors and `git diff --check`
passed. No live inference or paid provider requests were used.
