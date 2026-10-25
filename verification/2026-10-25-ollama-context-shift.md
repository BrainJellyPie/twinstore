# Preserve context while native Ollama generates

Disabling input truncation alone does not prevent a server from dropping earlier
tokens after generation fills the context. Ollama v0.40.11 defaults context
shifting on for supported model families. A short, syntactically valid answer
after losing earlier conditions cannot be detected by JSON validation alone.

Native chat requests now send `shift=false` alongside `truncate=false` at the
top level. The cache policy advances from `preserve-input-v1` to
`preserve-context-v2`, excluding old answers that could have used shifting.
When the server reports a length cutoff, the existing typed rejection and
bounded application recovery apply without adding another client retry layer.

Pinned protocol evidence:

- [Chat handler](https://github.com/ollama/ollama/blob/v0.40.11/server/routes.go)
  passes the request's shift flag to runner scheduling.
- [Scheduler](https://github.com/ollama/ollama/blob/v0.40.11/server/sched.go)
  resolves the flag into `ContextShift` and treats it as a runner launch setting.
- [Runner](https://github.com/ollama/ollama/blob/v0.40.11/llm/llama_server.go)
  uses that setting for the context-shift argument and maps a limit stop to
  `DoneReasonLength`.

Because shifting is a runner setting, changing this policy can reload an
already loaded model; another client requesting a different shift policy may
also cause a reload. Older servers may not enforce these optional fields.

Fourteen new tests cover top-level transmission in five call modes and both
JSON modes, exclusion of the previous cache policy, and customer batches of
4, 5 and 12. Scripted native HTTP represents a short answer after forgotten
rows when shifting is enabled, and a length cutoff with bounded two-child
recovery when disabled. This fixture demonstrates the protocol consequence,
not a measured native-model failure rate.

Before repair: 14 failed in 1.95 seconds. After repair: 231 focused native
context, output-limit, schema, endpoint, customer and supplemental-summary
tests pass in 4.78 seconds. Full-source Pyright reports zero errors and
warnings. Tests emit 80 existing LiteLLM logging coroutine warnings. No paid
calls, weights, native inference or full suite were used.
