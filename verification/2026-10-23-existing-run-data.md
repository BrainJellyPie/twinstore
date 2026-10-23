# Preserve run data without a status file

Run admission checked only `status.json` when reserving a project-wide run ID.
Legacy/CLI output, interrupted snapshots, and runs whose status file was lost could
therefore be accepted as new runs. Their later output would share and overwrite the
existing input/output paths.

Both the initial input load and the final reservation under the run lock now reject
an existing run directory. Empty directories also retain their ID: admission does
not infer that an incomplete directory is disposable. Newly generated IDs and new
explicit IDs continue to work.

Focused validation used fake submission and temporary local files:

- Before: 32 failures in 18.04 seconds. Existing summaries, store inputs, image
  manifests and empty directories were accepted without a status file, both before
  admission and when they appeared after input loading. Normal/preview and rule/
  vision combinations were covered.
- After: 69 passes, 12 unrelated image-render cases deselected, in 25.09 seconds.
  This includes the 32 new cases, existing concurrent-ID checks, snapshot cleanup,
  missing-snapshot handling and rule-image exclusion.
- Rejected admission leaves every existing file byte-identical, the layout in draft,
  no newly written status and no submitted worker.
- The concurrent test's observer now signals an attempted input load even when it
  rejects an already reserved image directory before pending status is published.
- Strict Pyright for the changed application module: zero errors or warnings.
