# Generated draft names and Unicode validation responses

Integrated `claude/online-shopping-features-ji7y0f` through `a6cf0162`
onto main `8db1f630`. The incoming changes number app-generated layout
names when already taken and return a readable 422 response when rejected
request text contains an unpaired Unicode surrogate. Explicit user names
and repeated saves retain their existing behavior.

Review found two edge cases in the incoming naming implementation:

- An edited layout's generated name was checked for uniqueness before its
  final 80-character truncation. Long source names lost the distinguishing
  suffix and could even reproduce the source's name. The helper now accepts
  a length cap and reserves suffix space while finding an unused name;
  layout edits request the existing 80-character limit.
- Two photo applications could choose the same unused name during preparation
  before either file existed. They now choose the final generated name inside
  the project tree/save lock after rereading the source. The expensive photo
  preparation remains outside that critical section.

Six new real API regressions cover short names, 80-character ASCII, Korean
and emoji names, retry stability, and concurrent single/multiple-photo
applications. Five fail and one passes against the incoming implementation;
all pass after repair. No model responses are needed for these save/encoding
conditions. These tests do not establish naming behavior for every possible
concurrent manual rename.

Verification passes 406 distinct backend API cases across 13 files: 177
core cases in 19.65 seconds and 229 other affected-save cases in 24.99 seconds.
Coverage includes starter, library-photo, product-edit, shelf-copy, combined
capture and optimization saves, replay/deletion races, source metadata and
Unicode/nonfinite validation responses. Both runs finish without warnings.
Strict Pyright reports zero errors/warnings; server boot and diff checks pass.
Frontend code is unchanged and inherits the previous 138 focused cases and
TypeScript/lint/build. Model behavior is unchanged; the preceding six full
CPU assortment runs and two small-category runs remain applicable.

Only CHANGELOG.md conflicted; both Unreleased additions are retained.
Released changelog text and v0.8.2 tag/assets remain unchanged.
Logs: `/workspace/scratch/draft-names-{before,core-tests,integration-tests,pyright,boot}.log`.
