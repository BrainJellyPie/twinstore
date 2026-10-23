# Receipt photo batch isolation and memory use

Receipt image decoding happened outside the existing per-receipt failure handler.
A bad photo therefore aborted the request and discarded successful readings from
the same batch. The route also loaded every upload before starting any reading.

The decoder now participates in per-receipt error handling, preserving ordered
receipt IDs and reporting unreadable images as empty readings with notes. Uploads
are consumed in the worker one at a time, limited to the per-photo maximum plus
one byte for oversize detection. Explicit image closure releases decoded pixels
on both model success and failure. Unreadable receipts continue to block review
approval until corrected or excluded; they are not silently accepted as sales.

## Verification

- Invalid bytes, truncated images, oversized files and excessive pixel counts at
  the beginning, middle and end of otherwise valid batches; all-bad batches.
- Real API responses retain successful matched lines and CSV rows, stable IDs and
  review failures for unreadable receipts. Model responses are stubbed offline.
- Explicit decoded-image closure on success and model failure; empty iterable and
  list inputs; lazy reads, size boundaries and the existing 100-photo limit.
- Before the changes, malformed-image isolation and image closure tests failed;
  all three upload streaming cases also failed against eager buffering.
- Focused pytest: 63 passed in 4.68 seconds across receipt photo isolation,
  streaming, upload limits, vision API, receipt review and vision engine tests.
- Pyright for both changed source modules: zero errors or warnings.

This bounds application reads, not the total multipart upload size or temporary
disk usage. The existing photo count and per-photo limits remain unchanged.
