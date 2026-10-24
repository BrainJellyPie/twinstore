# Shelf Lab history isolation

Photo edits, compliance audits and sim2real studies used six hexadecimal UUID
digits. Two distinct UUIDs with the same prefix reused the same directory:
photo edits replaced the old image, mask and edit metadata, while studies
replaced the saved job status and could attach an unrelated existing report.

All three now use the full UUID and exclusively create their destination
directory. If that exact directory already exists, registration returns HTTP
409 without writing files or submitting work. Existing short identifiers are
still accepted by the read paths; no stored records are migrated.

Offline verification:

- Nine focused cases cover each family: matching UUID prefixes, an occupied
  full identifier, and retrieval of a legacy short identifier. Prefix-collision
  cases failed before the fix with changed image/metadata or job-status bytes.
- 27 identifier, lifecycle/snapshot and Shelf Lab API cases passed in 8.51
  seconds. Image edits ran locally; queued model work was mocked.
- Strict Pyright on the changed module: zero errors.

No paid model calls or frontend changes were required. Package uploads and
other job families retain their existing identifier allocation for separate
review.
