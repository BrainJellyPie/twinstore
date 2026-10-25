# Short online model runs must receive a model decision

Integrated feature branch f1edf64e09951e87eb7d1564dd3aec3c521d726f,
including its unavailable-model guard, interview echo detection and release
preparation records. Main's intervening bug fixes remain intact. Entries stay
Unreleased: the imported v0.5.0 notes are preparation, not a published release.

The new six-decision failure guard missed short runs. One shopper with three
allowed decisions could finish entirely through rule fallback, even when the
model was unavailable throughout. A successful exit survey did not make those
browsing decisions model-driven.

ModelPolicy now retains its last decision failure. Before writing sessions or
results, the worker raises that failure if no model decision ever succeeded.
The existing error formatter marks the job failed with its cause. The six-failure
early exit remains; rule runs, recovered models and partial fallback after an
answer still complete normally.

After correcting two test-fixture values to the public schema (`text` policy and
boolean cart reminder), the new boundary suite reproduced 16 failures with three
positive controls passing. It covers offline, invalid and truncated responses,
survey-only success, text/vision modes, and actual LiteLLM/Instructor requests to
intercepted native Ollama and OpenAI-compatible HTTP in JSON/JSON-schema modes.
Two additional positive cases cover recovery and failure after a valid answer.

Validation: 224 focused tests passed in 15.44 seconds, including model cutoff
recovery, interviews and lifecycle, online API and cross-catalog intent.
Full-source Pyright reported zero errors and warnings; backend boot passed.
There were 35 existing LiteLLM asynchronous logging warnings. No paid inference,
model downloads or frontend runtime changes were involved.
