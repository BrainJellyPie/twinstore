# Recover an explicitly truncated online exit survey

The new exit survey used the shopper decision's 240-token output cap but omitted
the bounded cutoff recovery used for decisions. A provider-reported length
cutoff therefore discarded the whole survey immediately.

A terminal `IncompleteOutputException`, direct or wrapped by Instructor, now
gets one retry with twice the output budget. The shopper route, prompt and seed
stay fixed. Earlier cutoffs followed by a different terminal error, invalid
answers, access failures and rate limits do not increase the budget. A second
failure still excludes the survey instead of inventing ratings.

The existing local SDK harness now exercises both decisions and surveys through
actual LiteLLM/Instructor, with intercepted native Ollama and OpenAI-compatible
HTTP responses, JSON and JSON-schema modes, and text/vision policies. Before
repair, **16 regressions failed and 104 controls passed**. Additional terminal
exception cases cover direct, wrapped, earlier-only and last-only cutoffs.

After repair, **165 focused tests passed in 23.40 seconds**, including all 128
cutoff/error controls and existing online browser, survey and API checks.
Full-source Pyright reported zero errors or warnings, and backend boot passed.
The 31 existing asynchronous LiteLLM logging warnings remain. No model server,
paid inference or downloaded weights were used.
