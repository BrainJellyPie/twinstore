# Independent captured product facings

Capture-to-planogram conversion repeated the same mutable SlotItem instance for
every facing of a product. A three-facing captured shelf priced at 100 therefore
became 133 under one 10% category increase: the same object was updated three
times. Editing one facing changed all siblings, and bulk editing reported only
one changed placement. JSON storage happened to break the shared references, so
the same layout behaved differently before and after persistence.

Each facing now receives an independent copy at planogram construction. The
product fields and placement allocation are unchanged. Existing stored JSON
layouts already deserialize into separate instances and need no migration.

Verification:

- Baseline: 42 failed and 5 passed in 0.53 seconds.
- 104 focused tests passed in 3.05 seconds. Includes 36 price-change cases across
  requested facings 1/2/3/4/5/7/16/33/100 and -50/-10/+10/+50 percent, the existing
  32-facing row limit, JSON round-trip equivalence, individual edits, bulk-edit
  placement counts, face replacement, new captured racks and photo-offer mapping.
- Pyright on the changed planogram module: zero errors/warnings.
- No live model calls, full suite or frontend build.
