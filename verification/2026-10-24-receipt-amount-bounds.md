# Validate receipt amounts in the effective currency before caching

Finite OCR numbers could still be unusable: multiplying a very large USD amount
by 100 produced infinity, while smaller amounts exceeded the receipt domain's
browser-safe integer bound. Both failures happened after successful model
validation and caching, so retrying the receipt returned the same bad answer.

Check minor-unit conversion in the response model's validation stage, using the
printed currency or the request's fallback currency after whitespace/case
normalization. Each request owns its validator so simultaneous receipts do not
share fallback currency. The conversion and domain models use the same existing
amount bound. A changed prompt asks for literal printed amounts and includes the
fallback currency, separating cache identities across those requests. There is
still only one correction attempt; repeated bad values fail without entering the
cache. No values are clamped or replaced with invented prices.

The offline HTTP matrix crosses unit prices, line totals and receipt totals with
USD, padded KRW, missing USD and blank JPY currencies; values include a finite
multiplication overflow, range overflow and a negative out-of-range amount.
Each case tests recovery on the second answer or repeated failure through real
OpenAI transport, LiteLLM, Instructor and caching. Controls preserve both signed
maximum supported zero-decimal amounts, including fallback currency, and verify
that simultaneous KRW and USD reads retain separate validation.

Before: 24 failing regressions and six passing boundary controls. After: 100
focused numeric, currency, receipt-review, vision-input and batch-isolation checks
passed in 4.13 seconds. Strict Pyright reported zero errors in both changed
modules; `git diff --check` passed. No live inference or paid model request was used.
