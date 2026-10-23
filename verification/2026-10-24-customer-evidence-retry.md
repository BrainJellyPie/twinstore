# Customer evidence survives partial generation

Customer uploads produce two independently saved artifacts: a text summary and a weekday/hour
traffic profile. Retry previously stopped reading the retained upload as soon as the summary
existed. A failure between these steps therefore completed on retry with no traffic profile,
even though the original file remained on disk.

The retry now reloads retained evidence regardless of summary presence. The pipeline skips
summarization when it already has stored text, and still fits/persists the visit-time profile.
The existing precedence of stored text over automatic summaries remains unchanged. No retained
uploads or existing customer records are deleted by this change.

The regression exercises the real start/background/status flow with inline execution and a
fake model: fail immediately after summary persistence, retry to completion, then run another
generation. It checks retained customers on failure, original hourly evidence, persisted traffic,
and no repeated summary calls. Cases include UTF-8 BOM CSV, CP949 CSV, XLSX and preexisting text.

- The initial fixture had fewer than the existing 200-visit fitting minimum and was corrected
  to 300 receipts before the meaningful baseline; those fixture failures are not product bugs.
- Valid baseline: 6 failures in 2.79 seconds, all losing the traffic profile on retry.
- After: 82 passed in 6.59 seconds across retry, upload retention, project metadata coordination,
  empty-regeneration preservation and CSV formats.
- Strict Pyright for `application/generation_async.py`: zero errors/warnings.
- No live model calls, full suite, frontend edits or release asset changes.
