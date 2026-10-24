# Resolve bounded pack targets without linking another product

Pack-reading model output limited shelf_product to 120 characters while layout
products can have longer names. A copied prefix lost the automatic link. If
another product had that exact 120-character name, the image linked to its SKU
instead, and the incorrect link was persisted.

Keep a private 120-character model response field, separate from the normalized
PackReading's full catalog identity. At the model field boundary, resolve a
prefix only when it identifies one case-insensitive catalog name. Reject shared
prefixes, including a complete shorter name at the same boundary. Below the
boundary, retain exact matching only. The prompt explains this copying rule.
Ambiguous readings still retain the valid read name, brand and other metadata.
The application's existing SKU ambiguity and concurrent-edit guards remain.

Before the fix, 16 cases failed and 24 controls passed in 3.88 seconds.
Scripted HTTP covers both JSON modes, Latin and Korean names, unique long names,
exact boundary names, longer/shorter collisions, insufficient prefixes, unknown
names, duplicate catalog rows and cached repeats. The JSON schema still sends
maxLength=120. API checks verify the exact saved SKU or absence of a link and
the full returned product name.

After the fix, 97 focused pack-reading, metadata, concurrency and project-lifecycle
tests passed in 6.16 seconds. Full source Pyright reported zero errors and warnings.
No native model inference or paid model calls were used.
