# Study commentary and deletion

Completed studies permit deletion while their optional AI commentary is being
generated. Both commentary writers previously saved with an unconditional parent
mkdir, recreating deleted study folders or even a deleted project directory after
the provider finished. Input reads also raced with deletion.

Study deletion now uses the existing project tree transaction. The A/B narrative
and four study-reading paths take an input snapshot under that transaction, release
it while calling the provider, and acquire it again to verify the project and study
still exist before saving. Deletion during the provider call succeeds immediately;
the late commentary returns 404 without writing. Deletion during a snapshot or commit
waits for that short file operation. Pending/running study deletion remains rejected.

Validation used temporary data and fake providers, without model/network calls:

- 30 boundary combinations cover five study types, deleting the study or project,
  and pauses at input read, provider response and final file write. All 30 failed
  before the fix once the staff-script fixture used its actual `staff-pitches` URL.
  The initial test draft had used the wrong URL for those six cases.
- The first focused run had 40 passes and three overly strict test expectations:
  after releasing an input snapshot, either deletion or the final commit may win
  the next lock. Those tests now accept 404 or success while requiring the final
  folder to remain deleted. All 30 boundary cases then passed in 5.80 seconds.
- The same focused run passed all 13 existing marketing lifecycle, study reading,
  and rule A/B API checks. The lifecycle fixture now creates real parent metadata.
- Strict Pyright for both changed application modules: zero errors or warnings.

Deleting a parent does not cancel an already issued provider request. It prevents
its late response from being persisted into a removed study.
