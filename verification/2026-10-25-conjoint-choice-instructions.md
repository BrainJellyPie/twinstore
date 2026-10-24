# Conjoint no-purchase instructions

Disabling the no-purchase alternative removed `none` from the choice schema and
task text, but the system prompt still explicitly offered it. That contradictory
request was reproduced in six HTTP cases: both JSON modes and 2/3/4 alternatives.
Eight enabled-option and invalid-response controls passed (2.42 seconds).

The system instruction now follows the configured setting. With no-purchase
enabled, shoppers can still decline every product. With it disabled, the prompt
asks for the most preferred displayed product. The schema stays strict; an
unsupported `none` answer is not converted into an invented purchase.

The regression uses the actual LiteLLM/Instructor clients and scripted HTTP,
records the transmitted instructions and schema, verifies exact choices and
checks cache reuse and setting changes. This establishes the request-contract
fix; no native local-model accuracy measurement or paid inference was run.

All 271 focused choice, design/estimation and personal-context checks passed in
5.71 seconds. Two existing LiteLLM logging-cleanup warnings occurred.
`uv run pyright src/` reported zero errors and warnings; `git diff --check` passed.
