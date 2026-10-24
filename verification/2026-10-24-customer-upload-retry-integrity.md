# Preserve customer-upload evidence on generation retries

Retained-upload reads treated missing or unreadable source files/receipts as no
attachment and queued customer generation without the uploaded evidence. Empty
or changed data and multiple possible source files were also accepted; a
wrong-shaped receipt produced an unhandled server error.

If a retained-upload directory exists, retry now requires a JSON object receipt
with a nonblank filename and exactly one nonempty readable source. New receipts
also store SHA-256; retry verifies the bytes against it. Inconsistent evidence
returns HTTP 409 with recovery instructions before reserving a generation or
queueing model work. Existing customers are preserved. Intact legacy receipts
without a digest remain supported, as do projects without an upload directory.
Legacy receipts cannot detect content changes that predate digest recording.

Offline verification:

- Nine initial cases failed before the fix: missing receipt, malformed JSON,
  wrong-shaped receipt, missing filename, missing/empty/changed source, ambiguous
  sources and read permission failure. All now return the intended error without
  queueing work or changing customers.
- Intact new and legacy receipts pass the exact original bytes and Unicode
  filename into the queued retry.
- 33 focused integrity, generation-start concurrency, missing-project and
  retained-upload-after-summary checks passed in 6.85 seconds.
- Strict Pyright on generation_async.py: zero errors. Workers were mocked; no
  model services were called.
