# Optimization job history isolation

Optimizer registration used the first six hexadecimal UUID digits as its job
identifier. Distinct UUIDs sharing those 24 bits overwrote the same status file,
left an unrelated previous result attached to the new job, and could erase the
entire previous result directory when registration failed.

New jobs use the full UUID. Registration exclusively creates the destination
directory before writing status or copying vision inputs. An occupied identifier
returns HTTP 409 without submitting work or changing existing files. Failure
cleanup applies only after this request successfully created the directory.
Existing short identifiers still load through the same read paths.

Validation was offline, without paid model calls:

- Six focused cases: two distinct UUIDs sharing a prefix, occupied legacy/full
  identifiers with successful/failing registration, and legacy-ID read support.
  Before the fix: five failed, one passed. The failures included overwritten
  status and complete deletion of a previously saved result directory.
- 33 focused identifier, input-snapshot, image-snapshot and optimizer API tests
  passed in 20.41 seconds, including rule-search completion and application.
- Strict Pyright on the changed application module: zero errors.

This change protects optimizer registration. Other job families retain their
existing identifier allocation and will be reviewed separately. No old IDs or
saved outputs are migrated.
