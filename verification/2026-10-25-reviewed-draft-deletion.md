# Keep reviewed layout operations inside existing projects

The same eager-directory/inside-project lock race affected shelf copying, library
photo assignment and reviewed text edits. Capture-batch saves created their output
directory before entering the project transaction. A library-photo preview could
also write image snapshots after the project was deleted and return success.

Move the three independent feature save locks into the external setup-lock folder,
remove eager layout-directory creation, and protect photo snapshot writes with the
existing project transaction. Capture-batch's internal lock is already acquired
inside that transaction, so only its early directory creation is removed. Existing
contention tests now hold the external locks at their new paths.

Eight concurrent HTTP regressions cover path/lock boundaries and the late photo
preview. All failed before repair in 3.47 seconds. After repair: 207 focused save,
preview, concurrency, retry, deletion and asset tests passed in 13.55 seconds.
Full-source Pyright reported zero errors and warnings; backend boot passed.
No real model calls, model downloads or frontend changes were used.
