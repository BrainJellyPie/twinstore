# Integrate online interviews without resurrecting deleted data

Merged `claude/online-shopping-features-ji7y0f` at
`1b947e5dbe7a8c9d2890e38b7b4a6f841b029f65`, including post-visit shopper chats,
step citations, saved conversations and six-language UI. The updated AGENTS.md
explicitly includes this interview's English prompt and Language directive.
Existing pagination, model-work estimates, ad identity and recovery repairs
remain intact.

The new interview path could recreate a deleted project or run when a pending
model answer finished. Acquiring its lock could also recreate the run folder.
Locks now live in the existing external project-lock directory. Reading the
visit and saving/resetting the conversation use the project's online write
transaction. A final run-existence check prevents late saves after run deletion;
model inference itself remains outside the project lock.

All 10 new lifecycle reproductions failed before repair: project/run deletion
during model preparation, immediately before writing, deletion first, and
ask/clear lock acquisition after deletion. Two additional controls verify that
a simultaneous question or reset still receives 409 while the first answer
completes and remains saved.

57 distinct focused backend tests passed (55 integration checks in 29.88 seconds,
then all 12 lifecycle cases in 5.97 seconds). Full-source Pyright reported zero
errors and warnings; backend boot passed. Frontend online and catalog checks:
102 passed in 13.22 seconds. TypeScript, changed-file ESLint with zero warnings,
and production build (18.79 seconds) passed. No real model calls or new release
workflow was needed.
