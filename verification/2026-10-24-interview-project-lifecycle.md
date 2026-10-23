# Interview persistence and project deletion

Personal interviews, generated follow-up questions and group transcripts checked the run
before saving, but deletion could happen between that check and the write. The writer then
recreated the project. Personal/follow-up file-lock acquisition could recreate folders too.

All three workflows now snapshot inputs and commit outputs under the project tree guard,
with provider calls outside it. Personal transcript locks use the existing external project
lock directory and a run/customer-specific name. Asking, clearing and suggestions share that
lock; suggestion lock waits happen outside the project guard to avoid blocking an answer's
commit. Transcript filenames and the stale-conversation comparison remain unchanged.

- Baseline: 18 failed, 6 passed in 3.65 seconds.
- First focused run: 60 passed, 22 failed in 16.88 seconds. All failures came from the older
  customer-ID fixture creating a run without project metadata. The fixture now includes the
  metadata present in actual projects.
- Final affected cases and resource-error checks: 62 passed in 9.10 seconds. Previously
  passing interview API, concurrency, suggestion-restart, empty-question and analyst lifecycle
  cases were not rerun after the fixture/error-precheck changes.
- Cases include deletion during model work, final persistence, deletion starting first,
  deletion immediately before lock acquisition, legacy and slash/Unicode customer IDs,
  and invalid/missing project/run errors. Existing arbitrary-ID cases cover long, combining,
  whitespace, punctuation and path-like identifiers and legacy transcript compatibility.
- Strict Pyright: zero errors/warnings for the modified application module.
- No live providers, frontend changes or full suite.
