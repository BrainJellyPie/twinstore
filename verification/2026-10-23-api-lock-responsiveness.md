# Busy layout requests leave the server available

Starting a run, importing products, cloning/deleting a layout and deleting a
project called blocking file-lock operations directly from async HTTP handlers.
A contended lock could therefore stop the server event loop for its ten-second
timeout, including status polling and unrelated health requests.

These five handlers now await their existing application operations through
Starlette's thread pool. The same locks, error responses and state transitions
remain in effect; a waiting request no longer occupies the event loop.

Focused verification:

- Before the fix: **9 failures**, 12.98 seconds. A real file lock was held while
  the protected request and health request used the same TestClient event loop;
  health could not respond before the lock was released.
- After the fix: **75 passed**, 12.79 seconds. All nine contention cases respond
  to health while still waiting, then finish successfully after release. Cases
  cover final/preview runs, slot imports, all three clone modes, layout deletion
  at both tree/layout locks, and project deletion. Existing save/start races,
  deletion safeguards, creation and slot-import tests also pass.
- Backend strict type check: **zero errors/warnings**. The API regression tests
  import the production app; startup hooks and background model jobs are disabled.

Frontend source is unchanged. No real project data or live models were used.
Full suites were not repeated under the user's focused-validation policy.
