# Preserve model answers when optional caching fails

Capture and marketing enable response caching automatically. A successful model
response previously became a failed operation when cache directory creation,
temporary writing or atomic replacement failed. A full disk could also leave a
partial temporary file. Reading an unavailable cache is already optional, but a
filesystem error from the preliminary existence check could bypass that handling.

Read cache entries directly inside the existing error boundary, treating a missing
entry as an ordinary miss. Catch only filesystem errors when writing the optional
cache, log the failure and clean up its temporary file when possible. Preserve the
validated response and usage accounting. Existing destination entries remain intact
when atomic replacement fails. This does not suppress provider errors, schema errors
or failures to save the actual project result; those remain required operations.

Offline regression coverage crosses synchronous/asynchronous calls and text/image
inputs with a file occupying the cache directory, denied directory creation, disk
full after a partial write, locked destination replacement and unreadable entries.
It checks that inference runs once, usage is retained, temporary files are cleaned
up where storage permits and a failed replacement preserves the old entry. A
separate control confirms that an unavailable model still reports failure.

Before: 16 failures and 5 passing controls. After: 91 focused cache, malformed-entry,
provider-reroute and key-fallback checks passed in 3.72 seconds. Strict Pyright on
the changed production module reported zero errors; `git diff --check` passed.
No live model or paid calls were made. Storage faults are injected deterministically;
the filesystem is not filled and system permissions are not changed.
