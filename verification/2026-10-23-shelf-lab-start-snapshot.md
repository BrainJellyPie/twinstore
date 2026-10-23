# Reserve Shelf Lab work against deletion and input changes

Audit and photo/render comparison startup read inputs and then registered jobs without joining the
project's save/delete transactions. Deletion could finish first and a late start recreated job folders
under a deleted project/capture. Starts could also read the old customer list while an accepted save
was still writing. Audits read traffic metadata inside the worker, so a starting estimate of 100 could
become 1 or 900 before the report completed.

Capture Shelf Lab inputs and pending registration under the existing project/layout transaction.
Capture deletion joins the tree transaction before checking active jobs. Audits capture the visitor
scale alongside their customers, before registering pending work; later metadata edits leave it intact.

Focused evidence:

- Audit/photo-comparison × project/capture deletion × both orderings, using real saved capture inputs.
- Accepted customer saves, locked tree/layout starts without pending jobs, and two later traffic edits.
- Before the fix: **16 failed in 3.66s**.
- New cases plus existing sim2real response/failure checks: **24 passed in 6.22s**.
- Strict Pyright on both changed modules: **0 errors**.

No live model calls, full suite, frontend or release binary changes. These checks cover Shelf Lab startup
and capture deletion; they do not claim every asset-upload/edit lifecycle has been audited.
