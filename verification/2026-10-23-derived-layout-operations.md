# Derived layouts retain operating conditions

Creating an edited layout silently dropped its saved operations. A store with
finite stock and staffed tills could become a draft whose ordinary run gave each
shopper independent, unlimited inventory. Merely changing a product photo could
therefore change the simulation conditions. Standard layout copies already
preserved these settings, but specialized creation workflows did not.

Product edits, shelf reuse, starter filling, library-photo assignment, text
edits and individual/combined shelf captures now carry the source's saved
operations into the child. Sources without operations remain unconfigured.
Existing replay handling returns the accepted result without resetting settings
subsequently edited on that child.

Optimization application retains the job's recorded operations, rather than
the current source settings: the saved result should use the conditions under
which it was evaluated. A search with shared-store behavior disabled remains
disabled even if the source now has saved operations.

Focused verification, using disposable data and no live model calls:

- Five editing workflows before the fix: **5 failed / 5 passed**, 3.69 seconds.
- Capture/optimization reproduction: **4 failed / 4 passed**, 3.76 seconds.
- Editing, preview and replay regressions: **29 passed**, 4.69 seconds.
- Capture, optimization and actual rule-based run configuration regressions:
  **12 passed**, 4.31 seconds.
- Strict backend types after all changes: **zero errors/warnings**.
- API tests import and exercise the application. Frontend source is unchanged.

The 18 configuration cases cover configured/unconfigured sources, finite empty
backrooms, staffing, closed till hours, explicit run opt-out, source preservation,
retries after later settings changes, and optimization settings different from
the source's current settings. Full suites were not repeated, following the
user's request to prioritize discovery/fixes over verification.
