# Run analyst lock location — 2026-10-25

Run analysis held analyst.lock inside the run folder for the entire model call.
On Windows, an open lock-file handle prevents deletion of its containing project.
The analyst now uses a stable lock in the external project lock directory, shared
by answer and clear requests. Input/commit project guards and existence checks
are unchanged; a response to a deleted project is still rejected.

A Windows-style sharing-violation guard reproduces deletion returning 500 while
the original lock is open, both with and without saved conversation text. The
fixed path permits deletion and the late answer returns 404 without recreating
the project. The guard tracks handles across request threads (FileLock's normal
thread-local is_locked flag cannot observe another thread's held lock).

Validation: the corrected baseline had 2 failures in 3.20s; 25 focused analyst
API/lifecycle/echo/locking tests passed in 9.73s after the change. Full backend
Pyright: 0 errors, 0 warnings; server boot passed. Tests ran on Linux with Windows
open-file deletion semantics simulated; this is not a native Windows test run.
