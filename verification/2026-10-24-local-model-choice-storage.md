# Keep local-model Start/Stop effective when persistence fails

The manager claimed to keep a choice for the current session after a preference
write failed, but `chosen()` always reread the old disk value. An unsaved Stop
could therefore permit a later automatic startup; an unsaved Start could continue
to look disabled. If temporary-file cleanup also failed, the Start/Stop endpoint
aborted before acting on the process.

Remember explicit choices in the manager and serialize preference access with a
dedicated lock. Failed persistence keeps the new choice in the current session and
preserves the old file. Cleanup is best effort so the requested process operation
can proceed. A later successful write remains persistent across manager restarts.
The saved file is still the source of truth when a new manager has no session choice.

The start route also performed its synchronous preference write on the server
event loop. Run it as a synchronous FastAPI handler so filesystem waits and the
preference lock do not block unrelated requests. Startup itself still happens on
the manager's existing background thread.

Before: eight storage/choice regressions failed. A separate delayed-preference
test blocked `/api/health` while the Start endpoint waited. After: 65 focused
choice, lifecycle, runtime, readiness and API-responsiveness checks passed in
5.43 seconds; strict Pyright on both changed production modules reported zero
errors. `git diff --check` passed.

Tests cover both Start and Stop with denied directory access, failed replacement,
and failed cleanup; preservation of the old preference; a subsequent successful
save; and the real Stop API reaching process termination despite storage errors.
Model processes, downloads and storage faults are mocked. Persistence cannot
survive an application restart while its storage remains unwritable; the guarantee
in that case is explicitly limited to the current session.
