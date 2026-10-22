# Photo queue recovery — candidate selection

2026-10-22 UTC. Documentation/code-based hypotheses, not user interviews, market validation or measured task times.
Started clean at operator `e602be2e`. Integrated main `3970ff65` and AI UX `c0840349` as `5c354cf3` / `98c4d720`,
preserving starter filling, product editing and late-response ownership guards. English capture UI is retained.

Scenario: an operator selects several shelf photos, chooses recognition settings and starts the queue. Reloading
or leaving loses the unsent files and stable upload request IDs held only in `CaptureUploadQueue` component state.
Accepted recognition continues on the server; blindly uploading again with new IDs can create extra attempts.
A marketer preparing alternate displays and a researcher/teacher assembling a repeatable fixture face the same
setup interruption. Existing batch upload, per-photo review, crop registration and combined placement already
exist. The preceding cycle filled empty racks with starter products; this cycle addresses photo-work recovery.

Public sources fetched successfully (HTTP 200), with relevant content inspected:
- [MDN IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API): transactional browser storage supports files/blobs.
- [MDN storage quotas and eviction](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria): quota failures and browser eviction mean a local copy is not a durable backup.
- [NN/g user control and freedom](https://www.nngroup.com/articles/user-control-and-freedom/): recoverable actions, clear exits and explicit user control.
- [Shopify variant images](https://help.shopify.com/en/manual/products/product-media/add-images-variants): bulk image assignment is a separate useful convenience, with variant/media constraints.

| Candidate / users | Required input and actions | Data/model, feasibility and existing coverage | Validation |
| --- | --- | --- | --- |
| Save and restore photo queue / operators, marketers, teaching | Explicitly save a browser recovery copy; restore paused; resume existing queue | Reuse files, exact names/settings and stable IDs with the existing idempotent upload API; no new model call on save/restore. Chosen | Reload, lost responses, quota/corruption, concurrent revisions, changed settings, file integrity, review-to-placement flow |
| Reuse a stocked rack / operators, researchers | Choose source and destination rack | Existing whole-layout duplication does not map one rack; requires rotated/internal/locked-face rules | Geometry/capacity, images, source preservation |
| Assign product images together / operators, marketers | Drop images and confirm SKU matches | Existing photo crops and product-library uploads partly cover this; filename/name matching cannot silently invent identity | Duplicate/ambiguous names, formats, partial upload failures |
| Natural-language whole-store creation / beginners | Description and interpreted constraints | Current AI UX drafts profiles, town and marketing tests; geometry needs further live model evaluation | Unsupported constraints, late responses, model/API failures |

Selection: extend the existing photo queue with an **explicit browser recovery copy**. Keep photo bytes private to
this browser until the user starts uploads. Persist exact upload intent (files, names, digests, IDs and settings),
not a claim that recognition has finished. Restore paused; Resume replays existing IDs to recover accepted jobs
without starting them again. Save changed intent before uploading when recovery is enabled. Browser writes use
transactional revision checks so another tab's saved copy cannot be overwritten. Quota/corrupt data failures leave
the live queue and previous stored copy intact. Clear/forget actions are explicit. No new CSV or analysis API.

No usage-time savings are claimed. Browser storage can be cleared/evicted; it is not cross-device/cloud backup.
Live model accuracy and actual store inventory/prices are outside this recovery feature's validation.
