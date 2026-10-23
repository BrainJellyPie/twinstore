# Floor changes and product removal commit together

The floor editor previously sent one request to remove existing products and
another to save the changed floor. A rejected second request needed a third
request to restore products. A disconnected browser or failed restoration could
leave only the destructive first step committed.

Confirmed floor edits and legacy reset now send one complete replacement.
The optional, strict boolean `discard_products` flag permits an item-free floor
replacement through the existing save lock. Running simulations and history
still block it. The replacement is validated before the setup is written, so
validation failure leaves the original file unchanged. The flag is not stored
as setup data. Regular saves omit it and retain their existing protection.

The UI no longer clears or restores products in separate requests. A lost
response can be retried with the same complete replacement. Existing product
removal confirmation and localized copy remain in place.

Focused verification:

- New API cases before the change: **7 failed / 3 passed**, 3.45 seconds.
- Floor replacement, save locks, simulation races and deletion checks:
  **41 passed**, 11.35 seconds. Rejected requests preserve original file bytes.
- Editor component tests: **30 passed / 5 files**, 6.38 seconds. They cover one
  confirmed save, refusal, lost-response retry, unchanged floors, ordinary
  edits, fixture movement and legacy reset errors. Initial regular-save
  assertions caught an unnecessary false flag; regular saves now omit it.
- Strict backend types: **zero errors/warnings**. Frontend TypeScript and
  production build passed; Vite build **16.93 seconds**.
- Changed-file lint: **zero errors**, one pre-existing fast-refresh warning in
  LegacyDetectModal. Existing bundle-size/plugin-time build warnings remain.

No live models or real project data were used. Full backend/frontend suites
were not repeated, following the user's focused-validation policy.
