# Connect generated preferences to localized catalog shelves

Both shopping planners matched category words against visible rack names and
descriptions. Catalog racks retain stable category IDs in `rack_desc`, but an
ID such as `fresh_produce` was one token while the model's `Fresh Produce`
preference was two. A Korean `신선식품·채소` rack carrying `바나나` therefore
had no matching product, and the plan silently omitted its intended purchase.
Korean category preferences on English shelves had the corresponding problem.

The shared planning catalog now includes the existing English and Korean labels
for recognized category IDs. Rule preferences and VLM entrance-plan matching
both consume those words. Product names, stored layouts, generated personas,
prices and schemas are unchanged; already generated preferences and cached
model plans benefit when their products are resolved. Custom rack descriptions
and product-code tokenization retain their existing behavior.

The new tests cover four catalog categories in both label languages across
USD, KRW and JPY, plus a custom-shelf/product-code control. Twenty-four real
LiteLLM/Instructor HTTP cases generate a customer and, for the vision path, an
entrance plan, then execute the trip and verify its SKU, unit price and revenue.
Both structured modes and repeated cached requests are covered.

Before the change, 23 tests failed and 26 passed in 2.82 seconds: eleven category
checks could not find a product and twelve HTTP shopping paths made no purchase.
Afterward, the focused category, customer-preference, plan-resolution, clipped
label, reachability, selected-offer and scenario checks passed 283 tests in
22.90 seconds. Full source Pyright reported zero errors and warnings. No native
model inference, model downloads or paid requests ran. The HTTP responses are
scripted; the checks establish that valid category choices can reach purchases,
not that any particular model will make those choices.
