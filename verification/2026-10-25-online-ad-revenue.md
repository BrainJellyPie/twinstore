# Separate other-product revenue from checkout adjustments

Ad lift subtracted the promoted product's gross line revenue from the total paid
amount. This classified coupons as lost revenue from other products and shipping,
service fees or add-ons as gains from other products, even when the order contained
only the promoted item. That produced false cannibalization/halo findings.

Compute the other-product difference from recorded order line prices and quantities,
on the same merchandise basis already used by product and ad attribution rows.
Total paid revenue, advertised units, advertising cost and incremental ROAS retain
their existing definitions. No historical reports are rewritten.

Eight regressions failed before repair (0.89 seconds): promoted-only purchases
with coupon/fee/add-on/100% discount adjustments, mixed baskets in both comparison
directions, and free/empty orders. After repair, 61 focused ad, session and reminder
tests passed in 19.00 seconds. Full-source Pyright reported zero errors and warnings;
backend boot passed. Frontend source was unchanged. No paid inference or model
weights were used.
