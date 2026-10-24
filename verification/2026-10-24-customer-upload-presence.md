# Missing customer-upload folders cannot silently change generation inputs

The retained-upload reader detected damaged files inside `supplemental/`, but
returned no attachment when the whole folder was missing. Removing that folder
after a valid upload reproduced HTTP 200 and queued generation without the
customer evidence. Initial upload-save failures were also logged and ignored.

New project metadata records whether an attachment was supplied before upload
persistence starts. Keeping an upload records the same fact; retrying an intact
legacy upload promotes that existing evidence to the metadata marker under the
project lock. A required but absent folder returns HTTP 409 before a generation
is registered. Save failures return HTTP 503 and do not queue work. Existing
customers remain unchanged; successful retries still use the original bytes.

The file and receipt format is unchanged. Old projects with neither this marker
nor any retained upload cannot prove whether an attachment once existed; they
retain their prior behavior. This change does not recover deleted evidence.
The error explains restoring the saved upload or attaching it to a new store.

## Validation

- The missing-folder API regression failed before the fix: it returned 200 and
  registered a job instead of returning 409.
- Metadata, directory, data-file and receipt save failures were injected. Each
  prevented queueing and preserved the existing customers. Restoring storage and
  supplying the same file permitted a successful attempt.
- New stores with/without attachments, a first save failing before retention,
  intact legacy receipts, folder loss after legacy migration, and existing
  damaged-upload, worker rejection and project metadata cases were checked.
- 82 distinct focused cases passed across the checks. The first run had one
  fixture-path error (it included `.data/locks` among projects); after correcting
  that fixture and adding legacy marking, the 20 directly affected cases passed
  in 3.53 seconds. The first run's 81 passing cases took 6.56 seconds overall.
- Final strict Pyright: zero errors and warnings. No live model calls.

```sh
uv run pytest tests/server/test_customer_upload_retry_integrity.py tests/server/test_persona_queue_failure.py tests/server/test_project_creation_identifiers.py tests/server/test_project_metadata_races.py tests/engine/test_key_fallback.py -q --tb=short
uv run pytest tests/server/test_customer_upload_retry_integrity.py tests/engine/test_key_fallback.py::test_the_uploaded_customer_data_remains_available_after_its_summary_is_made -q --tb=short
uv run pyright src/
```
