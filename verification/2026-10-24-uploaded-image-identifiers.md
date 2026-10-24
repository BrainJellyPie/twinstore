# Preserve uploaded product images and shelf captures

Product image uploads, shelf photo uploads and already computed capture saves
shortened UUIDs to eight hexadecimal digits and reused existing paths. Distinct
UUIDs with the same prefix could replace an earlier image and its metadata.

All three paths now use full UUIDs and reject an occupied destination with HTTP
409 before writing. Product images check both the PNG and its JSON metadata;
captures exclusively reserve their directory. Existing capture request-ID retry
behavior remains intact. Computed-capture persistence now uses the project tree
transaction, preventing a save from recreating files after project deletion.

Offline verification:

- Eight initial regression cases failed before the fix, covering matching UUID
  prefixes and occupied destinations (including image-only and metadata-only
  product assets). The prefix cases reproduced actual image/metadata replacement.
- Two additional cases exercise both orderings of computed capture persistence
  and project deletion: either deletion removes the completed save, or the save
  returns 404 after deletion; neither leaves orphaned project files.
- 97 focused identifier, upload queue, capture/project lifecycle, product-image
  lifecycle and capture batch cases passed in 20.05 seconds.
- Strict Pyright on both changed application modules: zero errors.

Background analysis was mocked; no model services were called. Legacy records
are not migrated or rewritten.
