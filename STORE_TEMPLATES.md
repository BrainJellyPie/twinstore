# Store layout templates

Everything about generating a furnished starting layout: the 82 store formats, product categories, entrances and
exits, seating, checkouts, reserved areas, multi-floor buildings and the floor editor. The [README](./README.md#store-formats-and-templates)
has the short version.

The **New store** wizard can start with a furnished template or an empty layout.
The initial layout uses your store name, type and opening hours, and is ready to
edit as soon as the project is created. Persona generation follows the existing
wizard flow; choosing a template does not make an LLM layout-generation call.

In a project, choose **New layout → Generate a store from a template**. Search 82
formats including hypermarkets, warehouse clubs, pharmacies, cafés, restaurants,
fashion boutiques, bookstores, electronics, pet supplies and design showrooms.
Each format includes its own generic product assortment.

The default maps collectively stock the full catalog across 139 categories, including the
new products and their available local photos. Departments are matched to each format:

| Format | Examples of included departments |
| --- | --- |
| Toy & hobby store | Toy vehicles, plush toys, educational toys, puzzles, model building, miniature painting |
| Baby & family store | Baby care, feeding, bath supplies, plush toys and learning toys |
| Pharmacies | First-aid tools, oral care, wellness, baby care and personal care |
| Coffee shops and bakeries | Coffee and tea, barista tools, bread, pastries and related retail supplies |
| Home and design stores | Linens, dinnerware, lighting, bathroom accessories and storage |
| Pet stores | Food, enrichment, grooming, aquarium, small-pet and bird supplies |
| Craft and sports stores | Relevant art, sewing, model, cycling, swimming, climbing and outdoor departments |
| Beauty stores and larger pharmacies | Facial skincare, makeup tools, nail care and shaving supplies |
| Tea shops and bakeries | Tea brewing tools and cake decorating equipment |
| Home stores and footwear shops | Pantry organization and shoe care, matched to the store |

The product categories shown in the template picker control these same stocked departments.
Available photos stay attached when previewing, saving and reusing a generated layout.
The new-store wizard enables automatic catalog selection by default when a model is configured;
otherwise it starts with the format assortment. Turning automatic selection off also uses
that assortment. Creating a template layout inside an existing project uses the format
assortment without a product-selection model call.

**Pet supplies superstore** uses a 36×28 industrial floor with pet-food, care,
walking, grooming, carrier and bedding displays along parallel aisles. It has
five checkouts and opens 09:00–21:00 daily. **Sports & camping outlet** uses a
34×26 Nordic loop for fitness products, camping gear, apparel and footwear,
with four checkouts and daily 10:00–21:00 hours. Twelve new pet accessories and
twelve outdoor products accompany these formats. **Pets & outdoor living**
combines them as two independent retail floors.

**Thai kitchen & tea** offers twelve noodle, curry, rice, side and drink choices
on a 24×20 botanical floor with eight four-seat tables and three counters. It
opens 11:00–22:00 except Wednesdays. **Turkish café & bakery** offers twelve
doner, flatbread, soup, sweet and drink choices on a 22×20 terracotta showroom
floor with six four-seat tables and two counters, open 08:00–22:00 daily.
**Thai dining & Turkish café** combines them in a two-floor building. These
formats model counter purchases; kitchen preparation and table service are not simulated.

**Art supply warehouse** uses a 36×28 industrial floor with art materials,
stationery, books, hobby kits and tools along parallel aisles, five checkouts
and daily 09:00–20:00 hours. **Beauty & fragrance outlet** uses a 32×24 minimal
floor with cross aisles, personal care, fragrance and wellness products, four
checkouts and daily 10:00–22:00 hours. **Creative & beauty center** combines
these two large retail floors.

**Indian curry house** offers twelve curry, biryani, bread, side and drink choices
on a 24×20 warm floor with eight four-seat tables and three counters. It opens
11:00–22:00 and closes Tuesdays. **Vietnamese café & pho** offers twelve pho,
banh mi, roll, coffee, tea and dessert choices on a 22×18 botanical loop with
six four-seat tables and two counters, open 09:00–21:00 except Mondays.
**Curry, pho & coffee** combines them as independent floors. These formats
model counter purchases; kitchen preparation and table service are not simulated.

**Compact neighborhood pharmacy** is an 8×8 care shop with one counter and a
central spine, open 09:00–19:00 with Sundays closed. **24-hour care pharmacy**
uses a 24×18 floor, cross aisles and four counters; it stays open 00:00–24:00
all week. Both model retail care purchases without prescription dispensing.
**Neighborhood care center** pairs the compact pharmacy with an upstairs care-supply shop.

**Mediterranean deli** offers twelve pita, mezze, salad and rice dishes on a
20×18 coastal floor with six four-seat tables and two ordering counters. It opens
10:00–22:00 and closes Mondays. **Mexican cantina** offers twelve burrito, taco,
quesadilla and side dishes around a central plaza on a 24×20 terracotta floor,
with eight four-seat tables and three counters, open 11:00–24:00 daily.
**Mediterranean & Mexican dining** joins them as two independent dining floors.
These formats model counter purchases; kitchen preparation and table service are not simulated.

**Community market hall** starts with a 32×28 botanical floor, a central plaza,
four four-seat tables toward the back and four checkout counters. Produce, meals,
bread, pantry goods and flowers are available daily, 8–20, at fixed pack prices.
**Creative design hall** uses a 30×24 Nordic floor with homeware, art materials,
books, jewelry and plant gifts around the plaza, three counters and no dining tables.
It opens 10–20, with Tuesdays closed. **Market & design commons** combines these
two floors; each keeps its own dimensions, design and opening days. Both formats
can use any of the eight layout patterns, custom seating and reserved areas.

**Weekend farmers' market** uses a 28×22 botanical floor with cross aisles, four
checkouts and produce, bread, pantry and flower displays. It opens only Saturday
and Sunday, 8–16, and uses fixed pack prices. **Station fresh-food market** is a
20×14 coastal shop with meals, salads and coffee, two tables toward the back and
three counters, open 5–24. **Cinema snack shop** has an 18×12 industrial floor,
three ordering counters, snacks, drinks and ice cream, open 10–24 with no seating.
**Weekday office cafeteria** uses a 28×24 minimal dining floor with sixteen
four-seat tables and four counters, open Monday–Friday, 7–19.
**Commuter shopping & lunch** combines the station market and office cafeteria.
**Weekend shopping & snacks** combines the farmers' market, museum gift shop
and cinema snack shop; each floor retains its own opening days.

**Airport shopping gallery** is a 30×24 luxury loop with travel goods, fragrances,
jewelry and electronics, four checkouts and 24-hour opening. **Hospital convenience
& gift shop** is an 18×16 cross-aisle store for meals, care goods, baby supplies and
flowers, also open all day. **Museum book & gift shop** uses a 16×14 Nordic floor
with books, art supplies and keepsakes, open 10–18 Tuesday through Sunday.
**Evening food court** has a 32×26 terracotta floor, twelve four-seat tables and six
ordering counters, open 16–24. Its purchases use the counter-ordering model.
**Travel retail & dining** combines the shopping gallery and evening food court;
**Hospital services center** combines convenience, pharmacy and care-supply floors.
All four formats support mixed table sizes, counter spacing, category selection,
custom hours and portable option files.

**Nordic lifestyle showroom** combines homeware, books and plant gifts in a 22×18
floor with browsing islands and pale ash finishes. **Retro diner & shake bar**
starts with six tables, two ordering counters and a cherry-and-mint interior on
a 20×16 floor. **Design shop & diner** combines them as two independent floors.
The diner uses counter purchases; kitchen and table service are not simulated.
Under **Operating hours**, set opening (0–23), closing (1–24) and open weekdays independently
for each layout or building floor. Blank hours and **Use format operating hours** restore the
format defaults, including its regular days off. Set 0–24 for all-day opening, keep at least
one weekday open, and use a closing hour later than opening; overnight schedules are not supported.
**Set hours for each weekday** starts from those shared hours, then lets you change
each day independently—for example, weekdays 08:00–20:00, Saturday 10:00–16:00
and Sunday closed. Every open day needs a valid window; at least one day must stay
open. Turning the option off restores the shared hours, while **Use format operating
hours** clears both kinds of customization. A weekday schedule overrides shared hours
and the format’s regular closures while enabled. These settings are saved, reused and
included in exported layout and building options files. The New store wizard continues
to use the operating schedule shown in its store form for the initial layout.
The resolved weekly hours and closed weekdays also appear in **Compare with default**,
**Review all floors** and expanded floor plans. SVG downloads include them in the
accessible description. Matching days are grouped; 00:00–24:00 means all-day opening.
The playback time axis covers the earliest opening and latest closing across all open
weekdays, so an early-closing day cannot hide another day’s evening activity.
In a building, **Apply operating hours to all floors** copies the current floor's effective
opening, closing and closed weekdays—or the complete individual weekday schedule—to
every floor, including resolved format defaults. Applying shared hours clears individual
weekday schedules on the other floors.
The preview beside the button shows the hours and number of open days before applying.
Hours that do not resolve to a valid schedule cannot be shared. Each floor can then be adjusted independently;
**Use format operating hours** restores only the current floor's own defaults.

**Apply a layout priority** combines common requirements: **Wide circulation** uses cross aisles,
3-cell gaps, short shelf runs and more room around tables; **More display space** uses dense parallel
aisles with 1-cell gaps and longer runs; **Open center, no seating** removes dining tables and uses
perimeter displays; **Takeaway service** also places two counters near the entrance on its wall.
**Compact café seating** adds four two-seat tables near the back and one ordering counter.
**Family dining** uses six six-seat tables (36 seats), 2-cell table clearance and two separated
counters. **Mixed party sizes** uses two tables of each size (24 seats in total), standard table
clearance and two separated counters. **Separated service counters** removes seating and uses
three counters with 2-cell spacing, a spacious central spine and short shelf runs.
These four choices place counters on the entrance wall. The café and family choices switch to
uniform table sizes; the mixed choice supplies its own counts. Current table rotation is retained.
Fixed table and counter counts need enough space: if the preview cannot fit, enlarge the floor
or adjust the counts and spacing. Choosing a priority changes nothing until **Apply priority**.
Review the listed changes before applying. Dimensions, product settings, design, operating hours and reserved
areas keep their current values. The preview checks capacity, and every applied field remains editable.
In a building, **Apply priority to all floors** applies the selected priority to every floor
and immediately opens the floor review. Counters placed near the entrance follow each floor's
own entrance wall. Each floor retains its dimensions, format, seed, currency, product choices,
design, operating hours, table rotation, brief and reserved areas. If a floor is too small for
the requested seating or counters, its review shows the capacity error; **Edit floor** opens
that floor so its dimensions, counts or spacing can be adjusted independently.

**Refill & bulk grocery**, **Care & mobility supply store**, **Fragrance concept boutique**
and **Bubble tea café** add refill packs, care aids, fragrance products and a dedicated tea
menu. Each includes twelve specialty products. Their defaults range from a 28×22 botanical
grocery with cross aisles and four checkouts to a coastal café with four four-seat tables.
**Daily essentials center** combines them as four editable floors. Refills use fixed pack
prices; bulk weighing, clinical consultations and prescription dispensing are not simulated.
Realistic and Photo views distinguish compact fragrance bottles, tea cups with straws and
dry refill packs. Cosmetic mists and perfume oils keep their non-food packaging, and
upright cups and fragrance bottles stay in a single layer on displays.
Under **Product categories**, **Products per category** limits each included
category to 1–16 distinct products; leave it blank for the full assortment.
The limit keeps display positions and seating unchanged, with repeated facings
of the selected products. **Shuffle assortment** picks a reproducible mix;
the same seed and category keep their selection across floor sizes and currencies.
Enter an **Assortment seed** directly to revisit a specific mix. Positive and
negative whole numbers from -9007199254740991 through 9007199254740991 are supported.
Empty, fractional, scientific-notation and out-of-range input must be corrected
before previewing, exporting or saving. Shuffle advances to the next seed and
stops at the upper bound. Seeds remain independent between floors, travel with
options files and saved layouts, and are copied by **Apply assortment to all floors**.
An imported layout or building file with an unsupported seed leaves the current settings intact.

Set a number beside an individual category to override that shared limit. For
example, use 3 for drinks and 12 for menu items while other categories follow the
shared setting. Clear an individual number to inherit the shared limit; **Use
shared limit for all categories** removes every override. Limits are 1–16 distinct
products, capped by the available catalog; uncheck a category to exclude it.
Excluded categories retain their numbers for later. Known categories absent from
the selected format also retain their limits without changing its products.
These settings persist independently for each floor and through options files
and saved-layout reuse. The POST preview accepts them as `category_product_limits`,
a map of category IDs to integer limits (at most 64 entries).

In a building, **Apply assortment to all floors** copies category exclusions,
the shared and individual product limits, and the assortment seed from the
current floor, then opens the review. Formats, dimensions, currency, design,
hours, seating and reserved areas keep their existing values. Each format
uses only its own categories. An exclusion list that removes every category
on another floor produces a review error; edit that floor to restore a category
before saving. Each floor keeps independent settings after applying.

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

Under **Seating starts near**, choose **Entrance** to place the first tables
closest to the entrance, or **Farthest area** to start away from it. Both options
follow the entrance's wall and position when you move it. They work with mixed
table sizes, rotation, independent table gaps and reserved areas. As the table
count grows, seating spreads into the remaining available floor. Circulation
space is still preserved; table counts that cannot fit return an adjustment
message. Each floor keeps its own choice in saved layouts and options files.

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

Combine eight patterns (parallel aisles, racetrack, central spine, central cross aisles, central plaza, free-flow islands,
open-center perimeter and showroom groups) with a custom grid up to 40×40 cells,
three display densities, left/center/right entry, one to twelve checkouts and shelf
variants. Ten saved interior palettes—classic retail, warm wood, minimal white,
industrial graphite, botanical sage, charcoal/brass, coastal blue and terracotta
clay, Nordic ash and retro cherry/mint—change walls, shelving,
counters and floor tint in Realistic view and Photo mode. Formats choose a suitable
default palette; each building floor can use a different one. Open **Custom interior colors**
to override walls, floor, accent bands/highlights or counter tops independently. The other
finishes still follow the palette when you change it. Each color has a **Use design color**
reset, and **Reset all custom colors** restores all four. Overrides use six-digit hex
colors, including pure black and white; they are saved in layouts and portable option
files and restored when reusing a layout. The floor tint also appears in previews,
comparisons and exported SVG plans. Classic view keeps its original asset materials.
The preview uses the same options as the saved layout. Shuffle changes
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
**Central plaza** keeps a centered rectangle clear of shelves and dining tables,
with shopping rows around it. Its width and depth are each one third of the interior
dimension, rounded down, with a minimum of two cells per side. A 32×28 floor has a
10×8 plaza; an 8×6 floor has a 2×2 plaza. The area stays clear in either shelf
direction and at every density. **Interior aisle gap** and **Maximum shelf run**
control the surrounding rows. Tables are placed outside the plaza, so explicit
seating counts may need to be reduced; automatic seating fits the remaining space.
Reserved areas remain clear even when they overlap the plaza. The pattern is saved
and reused in layout and building options files.
The perimeter pattern keeps its wall-based arrangement. Shelf direction is saved
with the other options and can differ between floors or layout alternatives.

**Left–right table gap** and **Back–front table gap** override the shared
**Space around dining tables** setting independently. Choose 1–4 cells in either
direction, or **Shared** to use the existing 1–3-cell setting. Directions follow
the floor columns and rows, even after a table rotates. The gaps separate
dining groups and keep nearby interior displays clear; reserved areas remain
walkable. Larger gaps reduce seating capacity. Default seating adapts; explicit
table counts that cannot fit return an adjustment message. **Use shared table
gaps** clears both overrides. Layout priorities that set table spacing also
restore the shared gaps. Options are saved independently for each floor.

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

Existing areas have **Move area to** shortcuts for all four corners and the center.
These keep the area name and size and leave the outer wall cells clear. **Swap
width and depth** keeps the start column and row; it is disabled when the new
rectangle would extend beyond the floor. Move the area first if it needs more room.
Moving can repair missing or out-of-bounds coordinates after a floor resize, but
never shrinks an area. Blank or oversized dimensions must be corrected first.
Resizing the floor itself leaves existing area coordinates unchanged.

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

In the new-store wizard, open **Customize layout** for detailed settings and the options-file controls.
Size, currency and the live floor plan remain available while these settings are folded.

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
current interior palette and custom color overrides across the building, including the resolved palette
when the selected floor uses its format default. Applying a floor with no color overrides
clears overrides on the other floors. **Apply currency to all floors**
uses that floor's price currency for every generated floor. Each action changes
only its named setting; floor labels, layouts, seating, reservations and briefs
remain independent. You can customize an individual floor again afterward.
These controls update the building being prepared; existing shopper budgets are
not converted.

**Apply size to all floors** copies the current floor's width and depth to every
floor, resolving blank dimensions against its selected format. The floor review
opens immediately so you can inspect each resized plan. Each floor retains its
own format, product choices, seating and checkout settings, reserved areas, design, schedule and brief.
If an explicit seating count or reserved area cannot fit, edit that floor or enlarge
the shared size before saving; invalid floors cannot leave a partially saved building.
You can resize one floor independently afterward. Sizes are grid cells, with widths
8–40 and depths 6–40.

**Space beside counters** reserves 0–3 empty cells along the checkout wall on either
side of each counter, clipped at the wall ends. Counters respect the selected spacing;
wall shelves and cold displays cannot fill those gaps. Gate cells remain usable.
Zero preserves the existing adjacent-counter layout. Format-default counts adapt to
the available space; explicit counts that cannot fit produce an error with ways to
adjust the floor. Spacing works on all four walls with near/away placement, is saved
per floor and survives reuse and options-file import/export (`checkout_clearance`).

Add up to 48 dining tables to any format. Choose **Seats per table**: two, four
(the default) or six, for up to 288 seats when the floor has enough space. Enter any
whole count from 0–48, or leave the field blank for the format default. Café and restaurant
defaults include seating; small grids reduce the default count to fit. An explicit
count that cannot fit returns a capacity message. Groups occupy 1×2, 2×2 or 3×2 cells
with clear circulation around it, appears in Classic and Realistic views, and can
be selected from any occupied cell in the floor editor. Preview summaries, building
totals and exported floor plans count the chairs actually shown. Each floor keeps
its own table size in saved layouts and reusable options. As with other fixtures,
the existing floor-edit unlock step clears product placements before editing.

Use **Table rotation** to turn every dining group on a floor by 90 degrees.
Two-seat groups then occupy 2×1 cells and six-seat groups occupy 2×3 cells;
four-seat groups keep their 2×2 footprint with the chairs facing the other way.
The preview and capacity check use the rotated footprint and keep the requested
clear space on every side. Each floor saves its own rotation; zero tables retain
the choice for when seating is added again.

Open **Mixed table sizes** and enable **Use mixed table sizes** to combine
two-, four- and six-seat groups on one floor. Set a count for each size, up to
48 tables in total; the total table count updates automatically. Larger groups
are placed first, then smaller groups use the remaining space. Every group keeps
the selected rotation, seating area and circulation clearance. An arrangement
that cannot fit reports which size needs adjustment; counts are never silently
reduced. Turn mixing off to use the same total with the selected uniform size.
The mix is saved with each floor and in reusable options files. Priorities that
remove seating set all mixed counts to zero. The structured preview API accepts
the same `table_mix` object as saved layout requests.

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
