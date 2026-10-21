# Store layout templates

Everything about generating a furnished starting layout: the 54 store formats, product categories, entrances and
exits, seating, checkouts, reserved areas, multi-floor buildings and the floor editor. The [README](./README.md#store-formats-and-templates)
has the short version.

The **New store** wizard can start with a furnished template or an empty layout.
The initial layout uses your store name, type and opening hours, and is ready to
edit as soon as the project is created. Persona generation follows the existing
wizard flow; choosing a template does not make an LLM layout-generation call.

In a project, choose **New layout → Generate a store from a template**. Search 54
formats including hypermarkets, warehouse clubs, pharmacies, cafés, restaurants,
fashion boutiques, bookstores, electronics, pet supplies and design showrooms.
Each format includes its own generic product assortment.
Under **Operating hours**, set opening (0–23), closing (1–24) and open weekdays independently
for each layout or building floor. Blank hours and **Use format operating hours** restore the
format defaults, including its regular days off. Set 0–24 for all-day opening, keep at least
one weekday open, and use a closing hour later than opening; overnight schedules are not supported.
These settings are saved, reused and included in exported layout and building options files.
Under **Product categories**, **Products per category** limits each included
category to 1–16 distinct products; leave it blank for the full assortment.
The limit keeps display positions and seating unchanged, with repeated facings
of the selected products. **Shuffle assortment** picks a reproducible mix;
the same seed and category keep their selection across floor sizes and currencies.

**Entrance wall** places the entrance on the front, back, left or right wall.
For a separate exit position, **Exit wall** can follow the entrance wall or use
another wall, such as a front entrance with a back exit. **Share entrance** keeps
both gates together regardless of any separate-exit wall in imported options.
On side walls, entrance and exit positions run from back to front. Back and side
gates stay one cell inside the corners so their wall is unambiguous in 3D; front
gates retain the existing positions. Near/away checkout placement uses the actual
entrance location. New pickup-area starting points also follow the selected wall;
existing reserved areas keep their coordinates.

Search matches names, descriptions and categories, ignores accents (`cafe` also
finds `café`), and accepts words in any order. **More format filters** narrows the
starting layouts by cell count and dining seating, or sorts by name, floor size
or seat count. **Clear format filters** restores the catalog without changing
the selected format or your layout settings. Size and seating filters describe
defaults; the selected layout can still be customized.

**Compare with default** shows your current layout beside the selected format's
original starting layout at the same cell scale. Compare floor size, displays,
products, seating, checkouts, reserved areas and interior design before saving.
Each plan can be expanded and downloaded as SVG. Opening or closing the comparison
keeps your settings unchanged and does not create a layout.

Restaurant and café starting points include a family restaurant, neighborhood
bistro, takeaway coffee kiosk, tea lounge and artisan bakery. Vintage boutiques,
hardware stores and toy/hobby shops add distinct assortments and interior defaults.
Formats can supply their own seating zone, checkout placement and palette; every
default can be adjusted before saving. Multi-floor starting points also include a
family shopping center and a vintage shop with an upstairs tea lounge.

**Neighborhood pizzeria**, **Sushi & roll shop**, **Noodle & ramen bar** and
**Juice & smoothie bar** each have a dedicated twelve-item menu. Their defaults
range from a compact botanical juice bar with two tables to a terracotta pizza
restaurant with eight tables, with different seating positions and checkout
counts. **Dining house** combines all four as independently configurable floors.
These formats model menu purchases at counters; cooking and table service are
not simulated.

**Korean casual restaurant**, **Burger & fries shop**, **Salad & grain-bowl café**
and **Ice cream & gelato parlor** add four more dedicated twelve-item menus.
They start with 12, 10, 6 and 3 four-seat tables respectively, using warm,
industrial, botanical and coastal finishes. **Neighborhood dining center**
combines them as four editable floors. Seating, assortment, entrance and exit
walls, checkout counts and clear areas can be adjusted separately on each floor.

The campus dining hall starts with 24 four-seat tables (96 seats), four checkout
counters and perimeter meal displays on a 32×24 floor, with weekday opening
hours. The **Campus hub** building preset combines a campus store, bookstore and
dining hall as three independently editable floors.

Footwear boutiques, baby/family stores and travel essentials shops add dedicated
shoe, baby-supply and travel-gear assortments. Their starting layouts use showroom
groups, a central spine and compact aisles, with distinct interior palettes and
checkout placement. **Family essentials center** combines baby supplies, footwear
and a family restaurant in a three-floor building.

The **Garden & outdoor center** starts on a 32×26 floor with four checkouts,
botanical finishes and garden tools, growing supplies, plants and homeware. The
22×18 **Art & craft supply store** combines painting and craft materials with
stationery and books. Both use central cross aisles. **Garden, crafts & café**
combines these stores with an upstairs café as three separate floors.

**Optical & eyewear shop**, **Jewelry & accessories boutique** and **Music &
instrument store** have dedicated eyewear, jewelry and instrument assortments.
Their defaults use minimal or luxury showroom groups and industrial free-flow
islands. **Large fashion outlet** adds a 32×24 racetrack floor with apparel,
footwear, bags, coastal finishes and four checkouts. **Style, sound & café**
combines eyewear, jewelry, music and coffee as four independently editable floors.

USD, KRW and JPY prices keep their currency with the saved layout and simulation
results. New-project shopper budgets use the chosen currency, and additional
layouts default to that project currency. Existing shopper budgets are not
converted when a different template currency is chosen; use matching currency
for a simulation, or start a separate project for that market.

Combine seven patterns (parallel aisles, racetrack, central spine, central cross aisles, free-flow islands,
open-center perimeter and showroom groups) with a custom grid up to 40×40 cells,
three display densities, left/center/right entry, one to twelve checkouts and shelf
variants. Eight saved interior palettes—classic retail, warm wood, minimal white,
industrial graphite, botanical sage, charcoal/brass, coastal blue and terracotta
clay—change walls, shelving,
counters and floor tint in Realistic view and Photo mode. Formats choose a suitable
default palette; each building floor can use a different one. The preview uses the same options as the saved layout. Shuffle changes
the assortment reproducibly; reset restores the format's layout defaults.

Open **Product categories** to choose which parts of a format's assortment to
stock. For example, exclude the beer/alcohol category from a convenience store
or household goods from a pharmacy. Excluded categories remove their generated
displays across cold walls, shelves and checkout areas. Keep at least one
category; **Restore all product categories** brings back the format's full mix.
These choices persist in saved alternatives, individual building floors and
exported options files. They control catalog categories, not ingredients or
dietary suitability; manually uploaded products use the existing product editor.
Additional design briefs are saved as editable notes, not interpreted as commands.

Choose **Expand floor plan** to inspect the current preview at a larger size,
with numbered rows and columns, a cell grid, seating and checkout counts, and a
list of reserved areas. Zoom up to 400% and scroll to inspect individual cells,
or choose **Fit floor plan** to see the whole floor again. Close it or press Escape to return to the same settings.
**Download SVG** saves the complete floor at any zoom level, including the grid,
fixture colors and reserved-area markers. The file contains the store name,
counts, color legend and reserved-area descriptions as accessible SVG metadata;
it uses no external fonts or images and can be opened independently.
Entrances have green **IN** markers, exits have rose **OUT** markers, and a shared
gate shows both labels in a split marker. These appear in thumbnails, expanded
plans and SVG exports, including gates placed on the back or side walls.
The creation dialog keeps its title and action buttons visible while the options
scroll, including on smaller screens.

Interior shelf rows can run left to right or front to back. This rotates the
interior pattern and its product-facing sides while keeping the entrance,
checkouts, wall fixtures, seating and reserved areas in their chosen locations.
**Interior aisle gap** overrides the density preset with 1–4 empty cells between
interior rows and shelf runs. **Maximum shelf run** separately limits adjacent
display cells to 1–8 before leaving a cross aisle. It follows the density preset
when unset (3 spacious, 4 balanced or 6 dense); patterns and reserved areas can
shorten runs further. Both options apply in either shelf direction.
A small racetrack layout drops its second row when both rows cannot fit the
requested gap. The perimeter pattern has no interior rows, so both options are
disabled there. Wall spacing and dining-table clearance remain separate; grid
cells do not specify a physical distance. The gap and run limit are saved and reused with
the other layout options.

**Central cross aisles** keeps intersecting horizontal and vertical paths clear
of shelves and tables through the interior. Their width follows **Interior aisle
gap**, or the density default when no gap is selected. These paths can reduce
seating capacity: automatic seating fits the available space, while an explicit
count that does not fit produces an error. Reservations remain clear, and manual
floor edits can change the generated arrangement later.
The perimeter pattern keeps its wall-based arrangement. Shelf direction is saved
with the other options and can differ between floors or layout alternatives.

Use **Keep areas clear → Add reserved area** to leave up to eight named rectangles
open for consultation, pickup, events or later customization. Set their starting
column and row (counting from 1 at the back-left corner), width and depth. Areas
must fit inside the outer wall cells, where the template keeps its doors and wall
fixtures. The preview marks reserved space with dashed outlines; generated shelves
and tables avoid it. Default seating adapts to the remaining space; an explicit
table count that no longer fits returns an adjustment message. Areas remain
walkable and do not add rooms or service behavior. Settings are saved and restored
for single layouts and building floors; subsequent manual floor edits can use the
space freely.

**Area starting point** offers custom, consultation, pickup, fitting,
demonstration and event-space rectangles. New areas fit the current floor;
pickup starts near the chosen entrance, consultation starts in a back corner,
and demonstration/event spaces start near the center. Names receive a number
when another area already uses the same name. You can edit every position and
dimension afterward. Starting points can overlap and retain the same walkable
clear-space behavior; they do not add rooms or service simulation.

To iterate on a generated layout, open **New layout → Generate a store from a
template → Reuse options from …**. This restores its format, dimensions, style,
seating, currency, seed and design brief. Save a changed version as a linked
alternative while preserving the source; floor alternatives keep their building
identity. Use the import option to copy manual fixture edits or uploaded products.

Use **Export options** to download a JSON file of the selected floor's generation
settings, including currency, assortment seed, reserved areas and design brief.
**Import options** validates the file and checks that the layout fits before
replacing the current generation settings. You can use it in another project,
in the new-store wizard or on an individual building floor. Import does not create
a layout until you save the form, and does not carry over the source layout's
name or parent link. Manual fixture edits and product uploads are not part of
this file; use the existing layout-copy or workbook tools for those.

In **Multi-floor store**, **Export building options** saves the complete list of
2–6 floors in one JSON file, with their order, labels and individual settings.
**Import building options** checks every floor before replacing the current
list; an invalid floor leaves your configuration intact. The new building keeps
the name entered in the form and receives new floor identities when saved.
Single-floor and whole-building files have separate import controls.

**Review all floors** shows every proposed floor at the same cell scale, with
individual dimensions, palettes, currencies, seating and checkout counts. A
summary totals floor cells, tables, seats and checkouts once all previews are
ready. Invalid floors show their own errors; **Edit floor** returns directly to
that floor's settings. Reviewing, expanding or downloading these plans does not
create the building or replace any options.

While configuring a building floor, **Apply design to all floors** copies its
current interior palette across the building, including the resolved palette
when the selected floor uses its format default. **Apply currency to all floors**
uses that floor's price currency for every generated floor. Each action changes
only its named setting; floor labels, layouts, seating, reservations and briefs
remain independent. You can customize an individual floor again afterward.
These controls update the building being prepared; existing shopper budgets are
not converted.

Add up to 48 dining tables (192 seats, four chairs each) to any format. Enter any
whole count from 0–48, or leave the field blank for the format default. Café and restaurant
defaults include seating; small grids reduce the default count to fit. An explicit
count that cannot fit returns a capacity message. Each group occupies 2×2 cells
with clear circulation around it, appears in Classic and Realistic views, and can
be selected from any of its four cells in the floor editor. As with other fixtures,
the existing floor-edit unlock step clears product placements before editing.

Set **Space around dining tables** to one, two or three cells. The generator keeps
that space free of other fixtures on every side of each dining group, including
between tables and wall displays. More clearance reduces the number of tables
that fit; default seating adapts, while explicit counts return an adjustment
message if necessary. This setting uses grid cells and applies during generation;
manual fixture movement checks bounds and overlap independently.

Choose where seating starts: front/entrance side, back wall, left, right or center.
Tables extend into neighboring space as their count increases, retaining their
circulation space. Checkout counters can use the default arrangement or be placed
near or away from the entrance. These choices appear in the preview and are saved
per layout or building floor, including when reusing settings for an alternative.

**Checkout wall** places the counter bank on the front, back, left or right wall.
Near/away placement uses distance from the actual entrance on the chosen wall.
Small checkout displays move with the bank, and cold or wall displays use the
remaining space. Side-wall capacity follows floor depth; front/back capacity
follows width. The default count adapts to available space, while an explicit
count that cannot fit returns an adjustment message. If the bank leaves no room
for the only included product categories, choose fewer counters or restore more
categories. Wall choices also travel with exported layout and building options.

The exit can share the entrance or occupy a separate left, center or right cell
on the chosen wall. Checkout counters and impulse displays leave both gates clear.
This supports separate arrival and departure routes; shoppers use the selected
exit after shopping. Choosing the same wall and position as the entrance keeps a shared
gate. Exit settings are included in previews, saved layouts and reused options.

Large formats now start with multiple checkout counters: six for the hypermarket,
eight for the warehouse club, four for the food hall, and two for the organic
market and wellness pharmacy. Choose **Format default** to adapt those counts to
a smaller floor, or set an explicit count from 1–12. Counts that cannot fit beside
the selected gates return a capacity message instead of silently dropping
counters. Saved explicit choices, including a single counter, remain explicit
when their options are reused. The preview shows the actual generated count.

The floor editor supports up to 40×40 cells, with zoom controls and a scrollable
grid that keeps fixtures readable on large floors and smaller screens. Width and
depth can be typed directly. Reducing the grid never deletes fixtures silently;
save reports fixtures outside the new bounds so you can adjust the floor first.
Select a shelf, counter, dining group or gate and use the move arrows to shift it
one cell at a time. The full footprint must fit in clear space; paired entrances
and exits move together. Names, designs and rotation stay with the fixture.
For longer moves, choose **Move to a cell** and click the new top-left position
on the grid. Occupied or out-of-bounds targets leave the fixture in place so you
can pick another location; **Cancel placement** or Escape cancels the move.

The 3D view fits the floor to the available screen when it opens or resizes,
including large 40×40 stores on a small screen. **Fit store view** restores the
whole-floor view after panning or zooming in Classic and Realistic modes.
Returning from shopper view or Photo preserves the previous framing; fitting
is available again after leaving those views.
On phones, the store view sits above the results and settings panel; scroll down
to reach the panel without squeezing the floor into a narrow side column.

Choose **Multi-floor store** to create 2–6 linked layouts in one operation. Start
with a department store, shop with upstairs café, pharmacy/wellness building or
restaurant/café, then select each floor to change its format and options. Floor
labels appear in the layout tabs. Each floor has its own simulation; cross-floor
travel, stairs, lifts and a combined building simulation are not modeled.

For an existing generated building, **Reuse building options from …** restores
the selected floor and the newest saved version of each other floor. Select a
different saved floor version, move floors higher or lower, duplicate a floor,
and change its options before saving a separate building. Each new floor records
its source layout; the original building stays unchanged.

Use **Find layout** beside the layout tabs to search saved alternatives by name,
building, floor, store format or design brief. Filter single floors or building
floors and switch directly to a result; the current layout appears first.

Grid cells are not measured square meters. Pharmacy templates cover retail OTC
care and wellness, not prescription dispensing. Café/restaurant templates model
counter purchases; tables reserve floor space but table service, dining time and
kitchen operations are not simulated.
