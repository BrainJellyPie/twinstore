# Starter products for existing empty racks — candidate selection

2026-10-21 UTC. These are source-based requirements hypotheses, not interviews, market validation or measured task times.

Scenario: an operator imports a floor plan or places shelves manually. Step 2 offers an Excel round trip and
an editor for products already present, but no deterministic way to put starter products on those existing
empty racks. A marketer wants a preserved baseline; a researcher/teacher wants repeatable scenario inputs.
The template picker already chooses formats, category exclusions, quantities, seeds and all-floor assortments;
recreating that flow would duplicate work and replace the user's geometry.

Public sources retrieved with HTTP 200 this cycle:
- [Shopify bulk editing](https://help.shopify.com/en/manual/shopify-admin/productivity-tools/bulk-editing): selecting objects and applying shared properties.
- [NN/g recognition and recall](https://www.nngroup.com/articles/recognition-and-recall/): show available choices instead of requiring users to remember category identifiers.
- [NN/g user control and freedom](https://www.nngroup.com/articles/user-control-and-freedom/): recoverable changes and user control.
- [W3C form instructions](https://www.w3.org/WAI/tutorials/forms/instructions/): communicate input requirements and limits.
- [MDN File System API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API): the photo-resume alternative needs browser-support, secure-context and storage lifecycle decisions; file handles can be stored in IndexedDB.

| Candidate / users | Input and actions | Data/model, feasibility and existing coverage | Validation |
| --- | --- | --- | --- |
| Fill existing empty shelves / operators, marketers, teaching | Select empty racks, assign shown categories, preview products, save a child layout | Reuse built-in catalog and reachability checks; no model/CSV; preserve geometry and every stocked rack. Chosen | Locked/internal/blocked faces, sparse slots, duplicates, currencies, stale layout/catalog, replay, browser save/reopen |
| Resume an unsent photo queue / operators | Reopen and reconnect files | Queue already exists; browser file access and durable file retention require explicit lifecycle design | Reload, changed files, privacy/storage limits and uncertain requests |
| Reuse a previously stocked rack / operators, researchers | Choose source and destination | A different useful path, but needs geometry/face mapping and mixed-price rules | Rotation, collisions, capacity and image/source preservation |
| Natural-language whole-store layout / beginners | Brief and interpretation review | Latest AI UX already drafts customer profiles, town descriptions and scenario settings; full geometry still needs live model validation | Unsupported constraints, late responses and model failure |

Selection: add a direct Step 2 path for empty shelf/fridge racks, using the existing catalog and simulation
reachability rules. Stocked racks are never changed, even when partly empty. Category suggestions use only
an exact existing catalog key in rack_desc; other choices must be explicit. Generic products and reference
prices are scenario examples, not detected inventory or actual prices. Save a new child layout; no time-saving
claim is made. This complements the last cycle's editing of already placed products.

Started clean at operator `3fa41ef6`. Integrated main `dcc48c34` and AI UX `6178cc7c`, resolving CHANGELOG
and route import conflicts by keeping both sides; integrated baseline `e0a23693`. Existing photo workflows,
operator modules and remote assistive features are preserved. UI remains English in this Step 2 feature.
