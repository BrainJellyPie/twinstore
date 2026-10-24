# Validate generated survey prices before conversion and caching

Price-sensitivity survey fields required finite nonnegative values but had no
upper bound. A USD response of 90071992547410 became 9007199254741000 cents and
was treated as a successful answer despite exceeding browser-safe integer
precision. Larger values could overflow during conversion after they had already
been cached, making repeated survey runs reuse the same unusable response.

Build the four price fields with a maximum derived from the actual minor-unit
multiplier, so zero-decimal currencies retain their supported range. The schema
and prompt invalidate the old response cache identity. Permit one structured
correction attempt before reporting a respondent failure; no price is clamped,
and other respondents continue normally.

Thirty-two offline HTTP cases cross all four price fields, USD/KRW, the first
out-of-range amount or a huge finite value, and correction or repeated failure.
They exercise OpenAI transport, LiteLLM, Instructor, survey conversion and cache
reuse. Only corrected prices are cached; repeated invalid responses produce an
error with empty price fields after exactly two requests. Six controls preserve
zero, one minor unit and the maximum supported USD/JPY amount.

Before: 32 failures and six passing controls. After: 66 focused survey, pricing
and price-sensitivity aggregation checks passed in 6.29 seconds; 13 unrelated
marketing checks were deselected. Strict Pyright reported zero errors;
`git diff --check` passed. No live inference or paid provider requests were used.
