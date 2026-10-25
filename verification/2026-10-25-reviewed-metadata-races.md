# Inherit current operating settings in reviewed branches

A source operating-settings save could already hold the layout lock while a shelf
copy, library-photo assignment or reviewed text edit read the previous settings
and committed a branch. The completed branch then missed the concurrently saved
operating conditions.

Read inherited operations and building metadata under the source layout lock
inside the project tree transaction, then commit the branch. The product snapshot
already reviewed by the user remains intact, and independent edits to the original
are preserved. Existing idempotent retries continue returning the saved branch.

Twelve concurrent HTTP cases cover all three workflows, source-store versus
operating-settings edits, and preparation-first versus editor-first ordering.
The text-edit fixture uses an editable layout rather than the bundled layout's
locked simulation history. Valid baseline: three failing operating-settings cases
and nine passes in 3.55 seconds. After repair: 169 focused save, metadata, deletion,
retry and asset tests passed in 12.40 seconds. Full-source Pyright reported zero
errors and warnings; backend boot passed. No real model or frontend runtime changed.
