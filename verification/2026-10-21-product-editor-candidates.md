# Product editing convenience: candidate selection

2026-10-21 UTC. Source-based requirements hypotheses, not interviews, measured usability or market validation.

Scenario: an operator has generated a stocked store or corrected captured shelves and wants to rename a few
products and change a group of prices. A marketer needs a preserved baseline for a price/POP variant; a
researcher/teacher needs an inspectable change set. The existing ready dashboard Step 2 offers Excel
export/import, which replaces all slot rows. ProductLibrary manages package assets, not shelf product data.
Photo review edits one capture before placement. There is no in-app bulk editor for already placed products.

Sources retrieved with HTTP 200 this cycle:
- [Shopify bulk editing](https://help.shopify.com/en/manual/shopify-admin/productivity-tools/bulk-editing): select products and properties for simultaneous editing.
- [NN/g user control and freedom](https://www.nngroup.com/articles/user-control-and-freedom/): recoverable operations and undo.
- [W3C form validation](https://www.w3.org/WAI/tutorials/forms/validation/): identify invalid inputs and explain corrections.

| Candidate / user | Required input and operations | Model/data / feasibility | Validation |
| --- | --- | --- | --- |
| Placed-product bulk editing / operators, marketers, researchers | Existing layout, search/select SKUs, edit names/prices/promo, preview, save a child draft | No model or new CSV. Existing SlotItem has no category; keep SKU/geometry/images/regular prices unchanged. Chosen | Repeated SKUs, mixed values, exact money rounding, partial patches, stale source, replayed saves, original preservation and real browser flow |
| Starter assortment entry / beginners and teaching | Format/size/categories | Latest template picker already supports category exclusions, counts, shuffle seeds and all-floor application; avoid duplication | Catalog coverage and preservation of existing products |
| Product image linking / marketers | Drop packshots and match existing SKUs | ProductDrop already supports multiple files; matching/recovery could be improved later, but another photo-focused cycle would narrow variety | Ambiguous names, reused images, partial failures, original package preservation |
| Natural-language layout creation / beginners | Short description plus interpretation confirmation | Existing scenario descriptions now cover run situations, not all layout parameters; full layout intent parsing needs model validation | Unsupported constraints, model failures, reproducible accepted parameters |

Selection: extend Step 2 with an editor, not another analysis tab. Changes are explicit scenario inputs,
not verified prices, stock or sales effects. All placements of a selected exact SKU are in scope, including
placements outside the search filter. Preview must show mixed prior values rather than silently choosing
the first. Save as a new child draft; keep the original available. No time-saving amount is claimed.

Starting operator `24fea6d9`; integrated main/edge-case `113ab237` and AI UX `877ac758` at `93235d52`.
Main contains further photo queue viewport recovery; preserve it. New editor UI stays English under AGENTS.
Before the full verification pass, integrated AI UX `a556a035` at `a71bacc9`: product image naming,
neighborhood description, run model-key choice and storefront failure recovery. The new product image
naming flow overlaps the packshot candidate above and is preserved rather than implemented again.
