# Stop missing custom endpoints before simulation starts

A stored/default model reference such as custom:served could outlive its server
address. Custom providers need no API key, and readiness skipped endpoint checks
when the resolved address was empty. The engine appeared available and the run
API created a pending job, leaving the OpenAI-compatible SDK to choose its default
host when inference began. A configured custom key did not fix the missing host.

Named local providers now require a resolved server address. The custom provider,
which has no default address, raises a Settings-directed validation error when
none is configured. Existing presets keep their own default endpoints. Engine
availability catches the error, and the run route rejects the request before
writing run metadata or changing the source layout.

All 24 new API boundary checks failed before the change. They cover absent
settings, null and empty addresses, with/without a custom environment key, both
LLM and vision engines, availability listing and run creation. Independent model
and rule engines remain available. The successful regression asserts no background
submission, no new run, no source-byte change and no probe of an invented host.
The baseline stubs background submission, so its wrongly accepted jobs never run
inference.

All 194 focused readiness, malformed-address, credential and provider-resolution
checks pass in 4.79 seconds. Full-source Pyright reports zero errors and warnings.
The run emits 60 existing LiteLLM logging/event-loop warnings. No paid model call,
native inference or full-suite run was performed.
