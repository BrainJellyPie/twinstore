# Complete care and home photos in default maps

Added 64 photos for the remaining skincare, makeup, nail, shaving, tea-brewing,
cake-decorating, pantry-organization and shoe-care products. The catalog retains
1,592 products in 139 categories and now includes 1,056 local photos in 66 atlases.
All eight departments have a photo for every product in their matching default
maps. Images remain attached through preview, automatic selection, saving,
realistic rendering and the VLM shelf grid, alongside names and prices.

Integrated upstream customer memory, shelf crowding, sold-out overlays, checkout
lines, operations comparison notes and narrower VLM price tags. Boundary tests
reproduced and fixed checkout lines being ordered by time since each customer's
entry instead of clock time, and waiting customers drifting away from the till.
Crowding now accounts for actual browsing durations, including visits longer than
ten minutes, and stops counting a visit at its exact end. Browser inspection also
found joined weekly-table headings on narrow screens; separated columns and a
keyboard-accessible horizontal scroll region keep every column readable.

Validation on 2026-10-22:

- Operations, memory, API and comparison checks: 106 passed in 23.29 seconds.
  Three browsing-duration/end cases failed before correction; seven boundary
  cases now pass, without modifying the input visits.
- Focused playback, queue, lab and comparison UI: 65 passed in 4.75 seconds.
  Both different-arrival queue cases failed before correction. They now cover
  normal checkout, abandonment, till anchoring and seeking backward.
- VLM/product charts: 1,093 passed in 100.24 seconds. New image endpoints and
  manifest checks: 84 passed in 6.64 seconds. All 36 new map/currency/photo
  coverage cases passed in 0.67 seconds.
- Strict backend types: zero errors; application boot passed.
- Full backend: 23,829 passed and one skipped in 1,199.09 seconds.
- Full frontend: 4,359 passed in 255 files in 231.85 seconds. Build passed in
  20.37 seconds; lint retained 19 warnings and zero errors.
- Browser automatic beauty-store creation passed with four care departments and
  eight pictured products in realistic rendering. Default footwear-store creation
  used stocked format defaults without a configured model; saved racks exactly
  matched the preview and realistic rendering loaded 38 product pictures.
- All 64 new image endpoints, four galleries, both VLM grids and both 3D views
  passed visual inspection. One browser fixture used an incorrect template label;
  correcting it to the actual "Footwear boutique" name resolved that test timeout.
- Actual replay, planning, applying the plan and replaying it passed in all six
  languages at 390 px and 1,280 px. Week and probability bounds were enforced;
  applied plans reproduced both daily outcomes and the two-week memory results.
  Wide tables' final columns remained reachable. Saved run files were byte-identical
  and no additional simulation was launched by the lab. Korean and Spanish mobile
  plus French desktop tables were visually inspected.
- All 66 original atlas files are included in the wheel, verified byte for byte.

Browser product selection and personas used controlled fixtures in disposable
storage. Operations tests used completed rule-based previews. No live model
completion, model download or paid simulation was invoked.
