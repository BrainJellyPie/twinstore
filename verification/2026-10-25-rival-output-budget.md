# Fit a complete rival shelf match list

The rival matcher requests up to 80 name pairs, each repeating both product
names. Its application client limited output to 1,500 tokens. A complete valid
answer for 80 ordinary English or Korean labels takes 2,484–4,092 Qwen3.5 tokens
in the compact/indented examples measured here. Even 30 indented Korean pairs
take 1,542 tokens. Truncation exhausted the existing retries and returned no
model aliases, so those products did not enter price comparison or venue updates.

The rival matching client now allows 6,144 output tokens. This changes only its
request ceiling; it does not force long replies or change the shared configured
model, storefront, package-reading or simulation budgets. The existing client
recovery still adapts an output ceiling that a vLLM server rejects as larger than
its remaining context. This does not guarantee that arbitrary maximum-length
catalogs and answers fit every local context window.

The new API regression cases use real LiteLLM/Instructor with scripted HTTP that
returns finish_reason=length below the measured answer size. They cover 8, 30
and 80 products; English/Korean labels; compact/indented answers; and JSON versus
JSON-schema output. Successful answers must survive comparison, venue adjustment,
repeat application without compounding, cache reuse and source-byte checks.
Before the fix, ten cases failed and fourteen smaller controls passed.

All 101 focused API, venue-transaction and local output-budget recovery checks
pass in 6.07 seconds. Full-source Pyright reports zero errors and warnings. There
are 25 existing LiteLLM logging coroutine warnings. Tokenizer-only measurement
and scripted HTTP do not establish native model response accuracy. No model
weights, paid calls or full-suite run were used.
