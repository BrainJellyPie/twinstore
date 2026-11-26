# Customer writing needs Claude's thinking

Store creation with `anthropic/claude-haiku-5-5` failed on v0.9.1 with
"Customer generation failed (1 of 1 requests to the model): the model's reply
was not in the expected form."

## Cause

Two changes meet in the customer-writing request:

- `LiteLLMClient` sends `thinking: {"type": "disabled"}` on every Claude
  request, so that a short shopper decision is not used up by thinking.
- v0.9.1 (commit `1c09d527`) checks each written customer against the one or
  two types of its own request row, where earlier versions accepted any type
  of that hour.

With thinking disabled, Claude Haiku 5.5 writes the right mix of people for a
ten-row request but not in row order, and often drops a row. The row check
rejects the answer, the correction request gets nearly the same answer back,
and after three attempts the request fails. The first request of a
generation is a single timed request, so its failure ends the whole
generation.

## Measurements

Real calls to `claude-haiku-5-5` on 2026-11-26, one ten-customer request each,
fixed location inputs, temperature 1, three attempts allowed.

| Request | Requests that wrote their customers | On the first attempt |
| --- | ---: | ---: |
| v0.9.1 (thinking disabled) | 3 of 10, 3 of 12 | not counted, 1 of 12 |
| Row identity spelled out in the prompt, thinking disabled | 3 of 10, 4 of 10 | 0 of 10, 1 of 10 |
| v0.9.1 prompt, thinking left to the model | 10 of 10, 24 of 24 | 9 of 10, 18 of 24 |
| This change, through the job's own client settings | 30 of 30 | 24 of 30 |

Of the 34 answers given with thinking disabled, 2 were valid row by row, 13
could have been assigned to the rows in another order, and 9 had fewer people
than rows. Making the row's identity explicit in the prompt did not help; the
model's thinking did. A request takes about 19 s with thinking (median of 30)
and about twice the output tokens of one attempt without it, against three
failed attempts before.

## Change

`LLMConfig.claude_thinking` (runtime only, default off) leaves the `thinking`
parameter out, so the model uses its own default. The customer-generation job
sets it. Every other request to Claude is unchanged: features with a short
answer budget, the shopper engines and the assistive tools still send
`disabled`.

## End-to-end checks

- API: `create-store` with the `urban_cvs` format, then the quick sample:
  60 requests, 600 customers written, none failed (166 s).
- API: the same with automatic starter products, three stores: all created,
  each first customer request passed.
- Browser: the new-store wizard in Korean (fill the form from a sentence,
  draft the customer profile, create, choose the 100-a-day sample): 700
  customers written, the store view opened (274 s).
- A six-customer preview run on that store completed with the vision shoppers
  and with the LLM engine.

Not tested: other Claude models, and other providers' reasoning switches,
which are unchanged.
