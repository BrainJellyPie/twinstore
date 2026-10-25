# Include an open menu when sizing the shopper screenshot

Screenshot height depended only on the page beneath an overlay. On an empty
cart, empty search, wishlist, help or settings page, a standard grocery menu
extended below the image. Its hidden actions, including Close menu, were still
offered to a vision shopper.

The renderer now draws overlays before the final crop and includes their bottom
edge in the required height. The existing 6,000-pixel canvas limit remains.
Page contents, active controls, numbering and click actions are unchanged.

Before repair: **21 regressions failed, 8 welcome-dialog controls passed**.
After repair: **61 focused engine/API tests passed in 20.00 seconds**.
Full-source Pyright reported zero errors or warnings; backend boot passed.
Coverage includes the five short-page types, desktop/mobile, both text sizes,
minimal home pages with both welcome-dialog types, and a scripted vision-model
choice that closes the menu from an empty cart. Existing template, rendering,
browser, run and replay API controls also passed. No live inference was used.
