# Rejected entrance plans cannot vote for purchases

An ensemble member could return `enter=false` together with a leftover item
list. Single-model planning correctly ignored it, but ensemble voting counted
its products and quantities. At an entry tie, one browsing vote and one
walk-out vote with three products generated an actual three-unit purchase.
Other mixes promoted a minority item or inflated the median quantity.

Actual HTTP clients, ensemble routing, the VLM planner and purchase execution
reproduced sixteen failures across text/image requests and both JSON modes.
Eight majority-walkout and valid-purchase controls passed (3.33 seconds).

Only entering plans can now support an item or its median quantity. The
threshold still counts all members that answered; the entry tie still enters,
and failed providers retain their existing treatment. The prompt also asks
for an empty item list on walk-out, while the harness handles disobedient
responses. No purchase is substituted and the model's other choices survive.

Regression cases verify executed SKU, quantity, price, revenue, checkout count,
exit, entry agreement, cached reruns, failed members and unchanged source
inventory. No live inference or paid model calls were used.

All 131 focused purchase-vote, VLM-plan, ensemble and category-resolution
checks passed in 17.98 seconds. Pyright reported zero errors and warnings;
`git diff --check` passed.
