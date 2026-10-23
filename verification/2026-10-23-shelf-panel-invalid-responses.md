# Shelf Lab invalid response accounting

Unresolvable choices had `resolved_by="invalid"` but an empty error field. The
panel summaries therefore counted invented products and ambiguous names as
successful no-picks, even reporting perfect render/photo agreement when neither
reply identified a product. Raw photographs additionally discarded model numbers
before resolution, turning a number-only reply into an explicit no-pick.

Invalid choices now carry an error and retain their resolution/reason diagnostics.
Raw photographs still resolve by name, but a number-only reply is invalid. Genuine
empty choices remain valid. Existing summary and job handling excludes failed
pairs, records condition error counts and rejects a job with no valid comparisons.
The same panel feeds paired merchandising comparisons, which now exclude these
invalid pairs as well. This does not change cached reports already on disk.

Offline verification:

- Initial reproduction: 14 failures and 5 passes in 0.60 seconds.
- 32 panel, existing Shelf Lab and API cases passed in 9.67 seconds. Includes
  invented names, duplicate names, missing/out-of-range marks, whitespace-only
  raw-photo names, genuine no-picks, successful choices, mixed failures in each
  condition, transport failures and terminal API job status.
- 3 additional merchandising pair cases passed in 0.40 seconds: invalid before,
  after, or both. Failed pairs cannot create an apparent choice change.
- Pyright on the changed engine module: zero errors or warnings.

No live model requests, full-suite run or frontend build was needed for this
backend-only change.
