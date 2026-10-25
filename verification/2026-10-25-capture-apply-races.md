# Coordinate photo application with metadata edits and deletion

Single/multiple photo application inherited operating settings from an early
snapshot, while combined-photo saving read them without the source layout lock.
An overlapping operations save or reset could therefore leave the new layout
with outdated conditions. The reviewed product/layout snapshot remains valid
and must stay separate from an independent edit of the original store.

Photo application also wrote capture links after releasing the project tree
lock. Deletion in that interval could be undone by a late status write, creating
an orphaned project/capture directory. Deleting a selected photo during
preparation could leave a newly active layout behind despite a 404 response.
Concurrent applications could overwrite one another's capture links.

The final application now holds the project tree and source layout locks while
checking that all selected photos exist, inheriting current metadata, saving
crops and the child layout, changing the active layout, and updating capture
links. Combined-photo saving also locks its final source-metadata read. Reviewed
products remain unchanged; source edits are preserved. Lock contention produces
a retryable application error. These locks serialize concurrent operations;
they are not a multi-file crash-recovery transaction.

The new 25-case suite reproduced 17 failures with eight controls passing in
4.49 seconds. Cases cover single/multiple/combined photos, operation updates and
resets, both edit orderings, reviewed products, project/capture deletion during
the final status write, removal during preparation, and concurrent applications.

Validation: 105 focused capture, reviewed-draft and upload-lifecycle tests passed
in 16.98 seconds. Full-source Pyright reported zero errors and warnings; backend
boot passed. Recognition fixtures are offline; no paid inference or downloaded
model weights were used. No frontend runtime changed.
