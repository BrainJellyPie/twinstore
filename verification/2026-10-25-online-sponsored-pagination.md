# Keep sponsored listing controls inside the screenshot

A valid desktop category page with 24 products, four sponsored tiles, a two-column
layout, large text, a cart notice and a cookie banner placed the cookie controls
at y=5983..6028 on a screenshot capped at 6000 pixels. The model's option list
still offered those clipped buttons.

Sponsored listing tiles now share the configured first-page product limit.
At least one organic result remains on that page. Later pages subtract the
reserved first-page slots from their offsets, preserving every organic result
exactly once. Paused, missing and unrelated campaigns reserve no slots; wishlist
paging and other ad placements retain their existing budgets.

Before repair, 18 new pagination/visibility checks failed and three small-page
controls passed. The 21 new tests exercise category/search/deals, both devices,
both text sizes, cookies and notices, previous/next navigation, totals of
1/4/24/25 products at limits 4/24, filtering, sorting and empty search.
After repair, 83 focused tests passed in 25.41 seconds, including existing
advertising identity/reporting, wishlist and browser tests. Full-source Pyright
reported zero errors and warnings; backend boot passed. No frontend runtime or
model provider changed, and no paid inference was used.
