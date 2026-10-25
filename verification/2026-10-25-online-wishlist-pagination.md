# Keep saved-product controls inside the vision screenshot

Wishlist pages rendered every saved product, unlike bounded catalog listings.
A valid wishlist of 36 products with mobile layout, larger text and quick-add
buttons reached the renderer's 6000-pixel height cap: 10 of 76 active controls
extended below the image. Their option numbers were still offered to the model
and the browse UI even though the products could not be seen there.

Wishlist pages now reuse catalog pagination and sorting with the store's
configured products-per-page limit. Only the saved products participate;
sponsored-slot placement does not reorder them. Next/previous navigation and
returning from a product preserve the wishlist page. Empty or removed entries
keep the existing empty-state message.

Before repair, **9 regressions failed and 3 controls passed in 0.74 seconds**.
After repair, **76 focused tests passed in 16.84 seconds**, including existing
online sessions and stock limits. New cases traverse every page at 4 and 24
products per page, on desktop/mobile with normal/larger text; they verify exact
saved-product coverage, unique page URLs, backward navigation and every active
control's bounds in the rendered screenshots. Full-source Pyright reported
**0 errors and 0 warnings**. No model calls were used.
