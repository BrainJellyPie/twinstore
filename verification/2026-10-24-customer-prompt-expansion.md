# Bound generated labels before repeating them in customer requests

Trade-area keywords and hourly customer types had list-size limits but no string
length limits. A small model could repeat a phrase inside one otherwise valid
field. The next stage copies those fields into each customer's specification,
amplifying one response across a five-customer local batch.

An offline probe used the Qwen3.5 tokenizer and Instructor's actual JSON-schema
message preparation. A repeated keyword response of 2,522 tokens produced a
13,201-text-token customer request; a repeated hourly-type response of 2,527
tokens produced 13,200. These counts exclude chat framing and output tokens, so
the customer request already exceeded the managed server's 8,192-token slot.
No model weights were loaded and no inference was performed for this measurement.

Use the existing `PersonaLabel` 120-character bound for both fields, and state the
short-label requirement in their prompts. Grammar-capable servers receive the
constraint in the response schema; invalid responses are rejected inside the
existing structured-response retry before customer work is scheduled. Empty lists
keep their existing recovery behavior. No silent truncation or guessed labels are
added. This fixes this particular amplification path, not every possible oversized
request built from user instructions or many individually valid labels.

Regression coverage checks lengths 119/120/121 for ASCII, Korean, Chinese and
emoji, including the referenced JSON-schema constraint. Six pipeline cases feed
repetitive English, Korean and emoji labels, then a valid correction; each writes
five distinct customers in one compact request. The initial run exposed 30
missing-bound/schema or downstream-failure cases. During verification the schema
assertion was corrected to follow `$ref` definitions. Final result: 178 focused
profile, customer, traffic, population and concurrency checks passed in 2.66
seconds. Strict Pyright reported zero errors; `git diff --check` passed.
