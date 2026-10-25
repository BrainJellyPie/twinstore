# Reject question echoes in physical-store interviews

The physical-store interview still accepted a question copied into the answer
field. That text was cached and saved as a shopper statement; group interviews
could then code the copied question into their themes.

A per-question response schema now rejects echoes of the current or earlier
researcher questions, using the existing Unicode-aware question normalizer.
Instructor supplies corrective feedback within its existing two-attempt budget.
The prompt asks explicitly for an answer to the latest question. Terminal echo
failures retain a specific error and never append a transcript; the existing
group workflow excludes those answers from theme coding and refuses groups
with no successful answers.

Extended the actual SDK echo/cache matrix to physical trips: all 32 new cases
failed before repair. Both native Ollama and OpenAI-compatible HTTP paths cover
JSON/JSON-schema, seeded/unseeded calls, recoverable/persistent echoes, earlier
questions, case/punctuation, manual retry and cached-answer revalidation.
Three API cases verify no transcript append, successful manual retry, all-failed
groups and exclusion of a failed response from partially successful themes.

Validation: 203 focused tests passed in 13.06 seconds, including both interview
surfaces, personal/shelf evidence, Unicode questions, API, concurrency and
project deletion. Full-source Pyright reported zero errors and warnings;
backend boot passed. There were 67 existing asynchronous LiteLLM logging
warnings. No paid inference, model downloads or frontend changes were involved.
