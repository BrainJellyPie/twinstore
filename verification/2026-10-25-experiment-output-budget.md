# Fit complete multi-product A/B proposals

The A/B drafting client capped output at 1,500 tokens while its prompt permits
four variants and its schema permits six changes per variant. Valid proposals
repeat target names and operation fields. A four-variant fixture with six tea
products consumes 2,317 English-name or 2,437 Korean-name Qwen3.5 tokens when
formatted with indentation. It exhausted the same insufficient budget on both
existing attempts and failed rather than filling the builder.

Only the A/B draft client now allows 6,144 output tokens. The shared configured
model and other study/simulation budgets are unchanged. This ceiling does not
force a longer answer. Existing output-budget negotiation still adapts to a
server's smaller remaining context; this change does not make arbitrarily
large inputs and answers fit every local context window.

Tokenizer-only measurements for the exact JSON fixtures:

| Names | Variants, six changes each | Compact | Indented |
| --- | ---: | ---: | ---: |
| English | 1 | 415 | 709 |
| English | 4 | 1,273 | 2,317 |
| Korean | 1 | 463 | 757 |
| Korean | 4 | 1,393 | 2,437 |

Tokenizer JSON SHA-256:
`5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`.
No model weights or inference were used to measure these counts.

Thirty-two regression cases cover native Ollama and OpenAI-compatible local
HTTP, both JSON modes, both name languages, one/four variants and both formats.
Scripted HTTP returns length cutoffs below the measured size. Complete variants
must survive application validation and caching, preserve all six target SKUs,
and leave the original store and shared configuration unchanged.

Before repair: 8 failed, 24 passed in 4.12 seconds. After repair: 127 focused
budget, draft API, target, offer and remaining-context tests pass in 6.76
seconds. Full-source Pyright reports zero errors and warnings. Tests emit 33
existing LiteLLM logging coroutine warnings. No full suite or paid requests
were used; scripted response behavior does not measure native model accuracy.
