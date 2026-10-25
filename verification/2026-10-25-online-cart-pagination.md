# Keep large-cart checkout visible to vision shoppers

A grocery cart with 48 distinct products and large mobile text exceeded the
6,000-pixel screenshot canvas. Checkout and removal controls were still offered
to the model even though they were outside its image. A 64-product cart also
overflowed with normal text and on desktop.

The cart now uses the store's bounded listing size (4–24 products per page).
Every page retains the full order summary and checkout action. Removing the
last product on a page returns to the preceding page. Paging does not change
cart contents, coupons, fees, quantities or the final order.

Before repair: **15 regressions failed, 5 controls passed**. After repair:
**96 focused tests passed in 28.60 seconds**; full-source Pyright reported zero
errors or warnings, and the backend boot smoke passed. Coverage includes all
64 products across pages, desktop/mobile, normal/large text, maximum-length
product names, USD/KRW/JPY, the 0/1/24/25-row boundaries, removal at page limits,
and scripted text/vision-model checkout from a later page. Existing stock,
wishlist, browser, session and comparison checks also passed. No live model
service or paid inference was used.
