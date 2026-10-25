# Require comparable stores for advertising effects

The run launcher accepts different stores and price/design variants, but ad lift
previously credited their entire revenue difference to any campaign present on
one side. Local template product IDs also overlap between unrelated catalogs,
so these comparisons could claim an advertising gain for different products.

Ad lift now requires equal currency, tagline, ordered category/product catalogs
and site options. Active campaigns shared by both stores must retain their
content and relative order. Store IDs, comparison names, provenance, notes and
timestamps may differ; paused ads do not invalidate a control. General paired
metrics, customer switches and each store's observed ad attribution remain intact.

Twelve regressions cover different catalogs, prices, stock, category names,
taglines, currencies, shipping, coupons, search settings, changed shared ads,
copy metadata and paused-versus-absent controls. Before repair: ten failed and
two passed in 0.72 seconds. After repair: 31 focused advertising and API tests
passed in 9.05 seconds. Full-source Pyright reported zero errors and warnings;
backend boot passed. No frontend code, saved reports or model weights changed.
