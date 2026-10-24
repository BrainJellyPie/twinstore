# Bounded recovery for oversized impulse prompts

Large valid layouts could exceed a local model's input context during the
impulse stage, even after planned-intent recovery succeeded. The entire shopper
then failed. Qwen tokenization of system and user text for a hypermarket with
ten planned products measured 8,500 tokens in JSON-schema mode and 11,247 with
Instructor's JSON-mode schema prompt. Chat framing and output are additional.

Only a terminal typed input-context rejection now triggers one recovery, and
only when the exposure catalog can be reduced. The selection request considers
all actually exposed offers plus the verified planned basket and individual
needs. It selects at most max(4, remaining product allowance) exact catalog codes.
One focused request decides actions; an explicit empty selection adds none.
The actual store, full exposure guard, quantity/budget rules and checkout remain
unchanged. Candidate validation has two attempts; the focused request has one.
Further context failures propagate. Earlier context errors followed by a
different failure, truncation, authentication, rate limits and invalid output
do not initiate recovery.

The candidate prompt omits navigation geometry and uses compact tab-separated
rows with JSON-escaped names and promotions. Prices, shelf levels and optional
visibility remain explicit. Token counts for full / selection / focused text:

| Layout | JSON-schema mode | JSON mode |
| --- | --- | --- |
| Urban, ten planned products | 6,028 / 4,265 / 1,693 | 8,190 / 5,575 / 2,751 |
| Art supply warehouse, four | 7,001 / 4,838 / 1,288 | 9,502 / 6,487 / 2,348 |
| Hypermarket, ten | 8,500 / 6,071 / 1,713 | 11,247 / 7,966 / 2,771 |

The hypermarket JSON selection remains near an 8K limit; these figures exclude
chat framing and output and do not guarantee capacity on every server. Oversized
shared context still fails explicitly. Measurements use the offline Qwen
tokenizer; no model weights or inference were run.

Eight HTTP baseline cases failed before the change. The completed focused
coverage contains 185 distinct cases across context recovery, personal needs,
planned baskets, compact catalogs, intent recovery and exposure scope. Both
structured modes, both route orderings, corrected candidate output, combined
intent/impulse recovery, cache reuse, exact purchases/payment, terminal error
classification, empty selections and metadata escaping are exercised. The final
combined scope run passed 103 tests in 6.25 seconds; the recovery file including
four additional metadata cases passed 44 in 4.62 seconds. Strict Pyright reports
zero errors. HTTP responses were scripted; live model candidate quality was not
measured.
