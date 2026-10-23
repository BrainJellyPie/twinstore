# Combined-shelf save retries respect deletion

A completed combined-shelf save used its layout file as the only record of an
accepted request. Deleting the layout removed that record; retrying the same
request recreated the layout with the same ID and returned success.

Layout deletion now writes a small ID-keyed deletion marker before removing its
file. Combined-shelf saves check that marker while holding the same per-layout
lock as deletion, so a retry already in progress cannot race past the check and
recreate a deleted file. Markers contain only a deletion timestamp and live
under the project's setup directory; deleting the project removes them too.

Lost acknowledgments retain their existing recovery: an intact saved layout
returns its earlier result, while one explicitly deleted by the user returns
409 and requires a new preview/request. Previously deleted layouts with no
marker cannot be identified retrospectively.

Focused offline verification:

- Original API reproduction: **1 failed**, 3.10 seconds; retry returned 200
  and recreated the explicitly deleted layout.
- Complete capture-batch and deletion-race files: **41 passed**, 6.29 seconds.
- Additional checks: **4 passed**, 3.57 seconds. They cover deletion after a lost response, both ordinary retry
  and concurrent delete/retry, and recovery when the saved layout still exists.
- Strict backend types: **zero errors/warnings**.

No live models or real project data were used. Frontend source is unchanged.
Full suites were not repeated under the user's focused-validation policy.
