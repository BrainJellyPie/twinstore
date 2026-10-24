# New-store creation preserves existing projects

The wizard shortened project UUIDs to eight hexadecimal digits and reused an
existing project directory. Distinct UUIDs with the same prefix replaced that
project's metadata, reset its customer file to an empty list, and selected a new
layout while retaining old layouts and run files under the same project ID.

New stores now use full UUIDs. Creation exclusively reserves the destination
directory before writing metadata, customers, layouts or state. An occupied
directory or file returns HTTP 409 without starting customer generation. Legacy
project directories remain unchanged; their identifiers are still accepted.
Layout preparation still happens before filesystem creation, preserving the
existing failure behavior for invalid templates and starter-product selection.

Offline verification:

- Ten initial cases failed before the fix. They cover shared UUID prefixes and
  occupied full/legacy/empty/file destinations, with and without a template.
  The prefix cases reproduced replacement of metadata and emptying of customers.
- 56 focused project-ID, wizard/template and customer-workbook-preflight cases
  passed in 6.16 seconds.
- Two additional simultaneous-creation cases passed in 3.11 seconds: exactly
  one request succeeds, the other gets 409, and stored metadata belongs to the
  successful request. Customer generation starts once.
- Strict Pyright on the changed module: zero errors.

Customer generation was mocked and no model services were called. Existing
projects are not migrated or rewritten.
