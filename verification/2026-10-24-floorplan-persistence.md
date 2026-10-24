# Floor-plan imports preserve existing layouts on save failure

Imports previously published the new layout and active selection before saving
the retained plan image outside the project lock. Directory/image failures left
an active imported layout despite HTTP 500. A deletion between the layout save
and image-directory creation could succeed, then have the import recreate the
deleted project's directory and return HTTP 200 for a nonexistent layout.

The plan image is now encoded before publication. Image bytes, the new layout
and the active selection are saved under the same project tree lock. Failures
remove the new image/layout files; the atomic state writer preserves the prior
active selection. The response is prepared before writes, and existing layout
or image destinations are rejected without overwriting them. Deletion during
plan reading returns 404 when the project is no longer present.

## Evidence

- Four of the first five regression cases failed before the fix: image-directory
  failure, encoding failure, active-selection failure, and deletion racing image
  creation. The layout-write failure was a passing control.
- A separate deletion-during-reading case reproduced HTTP 500 instead of 404.
- Partial image writes and real atomic replacement failure for `state.json` were
  injected. Existing files remained byte-for-byte unchanged. Occupied layout and
  image destinations were preserved.
- 27 focused tests passed in 6.36 seconds for initial persistence coverage and
  existing image/PDF/API behavior. All nine final persistence cases passed in
  5.69 seconds after extending coverage: 31 distinct cases overall.
- Final strict Pyright: zero errors and warnings. All imports used the classic
  offline reader; no model calls.

If storage also refuses rollback deletion, cleanup logs the affected new path
and preserves the original error. This does not promise recovery from arbitrary
filesystem failures or a process crash between separate file commits.

```sh
uv run pytest tests/server/test_floorplan_persistence.py tests/server/test_floorplan_api.py tests/engine/test_floorplan.py tests/engine/test_floorplan_pdf.py -q --tb=short
uv run pytest tests/server/test_floorplan_persistence.py -q --tb=short
uv run pyright src/
```
