# Traffic source integration and landing correctness

Integrated feature branch 4768ae62fcd0a63e6669e67f6fec47cde0f46efd, adding
direct, search-engine, social and email arrival mixes, landing pages, model/interview
context, arrival segments and CSV attribution. The price and planning fixes in
main were retained when resolving the changelog and six-language catalog.

Search arrivals previously ignored target terms unless an exact product ID was
set. Purchase missions normally carry terms, not an ID, so a popular unrelated
product in the category won even when an exact matching product existed. External
arrivals now use the existing smart matching algorithm independently of the
store's own off/exact/smart setting; explicit product IDs retain priority and an
unmatched query retains deterministic category/popularity fallback. Source site
options and the behavior of internal store search remain unchanged.

Product landings also appeared in report view counts but not the rule shopper's
comparison memory, delaying its purchase decision by an extra product. Initialize
that memory from the landing view.

26 boundary tests cover six-language terms across three internal-search modes,
missing targets/categories, no matches, explicit targets, out-of-stock matching
pages, and all four arrivals' view/funnel accounting. Baseline: 21 failed, 5 passed
in 0.90 seconds. Final: 73 focused backend tests passed in 31.61 seconds; 184 online
frontend and locale tests passed in 30.76 seconds. Full-source Pyright reported
zero errors and warnings; backend boot, TypeScript and changed-file ESLint passed.
Production build passed in 17.57 seconds with its existing chunk-size warning.
No paid inference or downloaded model weights were used.
