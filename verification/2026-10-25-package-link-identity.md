# Do not turn an absent package match into a product link

The package reader resolves an unknown, null or omitted shelf_product to an
empty string. The application previously included empty product names in its
name-to-SKU index. When one such SKU existed, an explicitly absent match could
therefore auto-link the uploaded image to that unrelated SKU. Padded catalog
names also failed otherwise valid matches, and normalizing only one layer
would risk selecting one of multiple equivalent names.

The engine and application now use trimmed, case-insensitive, nonblank product
name keys consistently. The reader retains the full catalog name as its match;
the application links only when the normalized name identifies one distinct
SKU. Different SKUs sharing that name remain unlinked, while repeated placements
of the same SKU can still link. A manual existing link is preserved. Empty or
unmatched readings still save useful name, brand and confidence metadata.

Twenty-four actual LiteLLM/Instructor HTTP cases run the application read flow
against persisted image metadata. They cover both JSON modes, empty/null/omitted/
whitespace/unknown matches, an all-blank catalog, padded names and bounded
prefixes, ambiguous names/prefixes, duplicate placements and existing links.
Each verifies the saved SKU, metadata, repeat cache use and unchanged source
image bytes and store data. Before the fix, twenty cases failed and four passed
in 2.78 seconds.

The focused package identity, bounded-name, optional-metadata, API and concurrent
edit-conflict suite passed 108 tests in 4.18 seconds. Full source Pyright reported
zero errors and warnings. There were 63 known LiteLLM asynchronous logging
cleanup warnings. Responses are scripted; no native inference, model downloads
or paid calls ran.
