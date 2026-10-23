# Preserve product artwork through workbook edits

Reimporting unchanged product rows removed their saved `image_url` values. In a
real library-photo workflow, two immutable photo references became zero although
the original image remained readable. This changed the artwork available to later
vision runs. The old slot API discarded even explicitly supplied image references.

Workbooks now carry existing references in a hidden `image_url` column, leaving
the visible image-insertion column available. Parsing and slot saving preserve
the reference. A successfully uploaded embedded image replaces the references
for its SKU, including multiple placements; otherwise the workbook's saved links
remain. Explicit null/empty references retain their clearing meaning.

## Verification

- Baseline: two API failures and all seven new workbook cases failed.
- Real library upload, immutable-photo assignment and slot reimport: keep, replace
  with a newly uploaded red image, and clear. Both photo placements and their
  reference prices are checked; retained image URLs return the expected PNG bytes.
- Hidden-column export/import for absent, immutable, SKU-query and package URLs;
  malformed metadata; successful/missing/failed embedded image replacement and
  unaffected SKUs. Invalid API values leave stored products unchanged.
- Focused backend: 23 passed in 4.38 seconds; frontend: 82 passed in 3.55 seconds.
- Pyright, TypeScript and targeted ESLint pass. Production build: 16.58 seconds,
  with existing bundle-size warnings. No model calls.

The column preserves references to existing assets; it does not embed a backup of
every image. Older workbooks without this metadata retain their previous behavior.
