# Verify resumed local-model byte ranges

The downloader treated an HTTP 206 response's Content-Length as all remaining
bytes. A server returning one partial range could therefore create a truncated
final model. A wrong starting offset could append duplicate or missing bytes.
`_download_model` subsequently reused any nonempty final file, so startup kept
failing without downloading a replacement. An HTTP 416 on a complete/stale `.part`
also repeated indefinitely on subsequent attempts.

Validate the Content-Range start, inclusive end and full resource size before
appending. Check the declared segment length when Content-Length is present, and
reject bodies longer than their declared range. Use the full resource size to
decide completion. Valid short segments remain `.part` files for the next resume;
unverifiable or inconsistent ranges are discarded so the next attempt starts clean.
HTTP 200 responses that ignore Range still replace the partial file normally.

A resumed HTTP 416 discards the stale partial and performs one full request. A
fresh request's 416 propagates, so this cannot loop. This deliberately downloads
again rather than promoting an unverified `.part` based only on a 416 response.
Cancellation before the replacement request prevents it from starting.

Before: 13 failing byte-range/recovery cases and 2 passing controls. After: 68
focused download, model lifecycle and preference tests passed in 5.62 seconds;
strict Pyright reported zero errors. Three additional controls covered repeated
416s, complete ranges without Content-Length and cancellation after 416 (all 18
download-range cases passed in 0.27 seconds). `git diff --check` passed. The existing
resume fixture now supplies the Content-Range required by a real 206 response.

All responses use small in-memory files; no model weights or binaries were fetched.
This verifies resumed-download framing and completeness, not a content checksum
or repair of final model files already corrupted by an earlier version.
