# Reuse a stocked rack — convenience candidates

2026-10-22 UTC. Source-based requirements hypotheses; no interviews, market validation or timed user study.
Repository `BrainJellyPie/twinstore`; clean operator start `c81191ec`. Integrated main `c537ad50` as
`51fae440` and AI UX `88bbe428` as `3d5223b8`. Kept newer shelf/concept draft ownership and precision guards,
all routed-draft tests, photo recovery, starter filling and bulk product editing. Resolved duplicate fixture
names consistently. Existing parastore directory is untouched.

Scenario: an operator has corrected the names, prices, promotions and images on one shelf and wants the same
arrangement on several empty shelves in the same store. A marketer needs repeated endcap assortments; a
researcher/teacher needs controlled repeated fixtures while keeping the original layout. Today whole-layout
copy, generic starter filling, photo combination and bulk product editing exist, but none transfers one
finished rack's exact slots to several compatible empty racks. Reentering each slot risks inconsistent values.

Public pages retrieved with HTTP 200 and relevant text inspected:
- [Shopify adding/updating products](https://help.shopify.com/en/manual/products/add-update-products): duplicate an existing product, with explicit handling of the duplicate's status/channels. Supports reuse as a convenience pattern, not evidence of demand in TwinStore.
- [NN/g User control and freedom](https://www.nngroup.com/articles/user-control-and-freedom/): visible exits, undo and return to the previous state.
- [W3C error prevention](https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html): reversible/checked/confirmed changes to stored user data. Used as design guidance, not a WCAG conformance claim.

| Candidate / users | Inputs and actions | Existing coverage, data/model needs and feasibility | Verification |
| --- | --- | --- | --- |
| Reuse one stocked rack / operators, marketers, researchers | Select source, compatible empty destinations, preview, save/open child layout | Real existing slot data; no model, new CSV or price inference. Whole-layout copy and starter fill do not cover exact rack reuse. Selected | Exact products/images/order/levels, blocked faces, occupied destinations, shape/orientation, stale inputs, save replay, source preservation |
| Bulk image-to-SKU assignment / operators, marketers | Drop images, review uncertain matches, apply | ProductLibrary already accepts multiple images, background removal and optional reading. Individual linking remains; further study must avoid duplicating upload | Duplicate/ambiguous matches, partial failure, filename/identity distinction |
| Natural-language store start / beginners, teaching | One description, review form/options | Latest AI UX already adds store-description setup and layout briefs/direct edits. Do not build a duplicate entry point | Late answers, unsupported constraints, model availability |
| Resume unfinished photo intake / operators | Save browser queue, restore/resume | Completed in preceding cycle; no duplicate implementation | Existing recovery tests retained |

Chosen scope: **Reuse shelf products** in existing Step 2. Copy exact nonempty slots to empty shelves/fridges of
the same type and rotated footprint, keeping absolute N/S/E/W sides, levels and within-slot order. Reject a
source or target whose copied product faces are locked, blocked or unreachable; never drop products to fit.
No replacement of stocked racks, physical stock inference, conversion, new SKU generation, image rewrite or
model call. Preview exact source products and destination counts; save an idempotent child layout with source
snapshot checks. Returning to the original layout undoes the variant. No measured time saving is claimed.
