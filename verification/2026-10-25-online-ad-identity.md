# Preserve campaign identity for repeated advertised products

Two active campaigns for the same product in the same tile placement previously
used a product-to-campaign dictionary. Its last entry replaced the first campaign
on both tiles. The first campaign disappeared from recorded impressions and its
clicks and CPC costs were assigned to the second campaign; CPM totals also missed
one campaign. A valid store can configure these campaigns independently.

Each ad tile now receives its own campaign ID when constructing product-open and
quick-add controls. Filtering paused or missing products, tile order and the
four-campaign placement limit are unchanged.

All 14 new regressions failed before the repair. They cover home tiles, sponsored
listings and product-page ads, repeated products, paused/missing campaigns,
separate clickable rectangles, quick add, text/vision model decisions and CPC/CPM
reporting. The model test uses fixed badge order to select the first identical
label deterministically. It runs the actual session and reporting paths with a
fake model, without paid inference.

After repair, 14 new tests passed in 1.52 seconds and 36 existing online-store and
advertising tests passed in the related check. Full-source Pyright reported zero
errors or warnings; backend boot passed. No frontend runtime changed.
