# Preserve source context when estimating visits

Customer generation supplied additional instructions and supplemental/neighborhood
evidence to trade-area analysis, but daily traffic requests received only its
identity labels. Quantities, weekday mixes and peak hours could not pass through
that label-only result. When revised evidence produced the same labels, the daily
request was also identical and could reuse traffic cached for older evidence.

Daily traffic analysis now accepts the same optional instruction and summary
inputs and appends each supplied value to its user message. This preserves the
evidence without another model call and includes it in cache identity. Empty
inputs leave the previous prompt unchanged. The existing opening-slot guard,
population cap, observed traffic-profile reshaping, probe/sample choice and
customer-hour assignment still apply.

Six real HTTP regressions failed before the fix. Both structured modes now carry
instruction-only, summary-only and combined evidence through Monday/Sunday
estimates. Changing from two visitors at 17h to four at 09h with identical identity
labels changes the generated hours/counts and estimate cache; repeating identical
inputs uses the cache. Separate controls preserve opening-hour boundaries even
when an instruction asks for closed-hour visits, and avoid empty prompt sections.

Focused traffic, customer generation, context recovery, sample/probe and
neighborhood integration verification passed 201 tests in 7.40 seconds. Strict
Pyright reported zero errors. The write-choice test fixture accepts the new
optional traffic context arguments while retaining its original assertions.
All model responses were scripted; this verifies context propagation and cache
separation, not the accuracy of real-model traffic predictions.
