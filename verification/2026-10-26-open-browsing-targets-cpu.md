# Whole-shop browsers retain no hidden category restriction

2026-10-26, based on main `eb9550cc`. The integrated browsing-goal change
(`1005085e`) gives three in four browsers a whole-shop goal. The generator
still returned the initially sampled category and its search terms. The model
saw a broad goal, while arrival selection, rule browsing and rival eligibility
continued to use a narrow category target.

A production-generated fashion shopper, seed 4, has this goal:
“Look around the shop out of mild curiosity, with no plan to buy; you move on
as soon as nothing catches your eye.” Its hidden target was `apparel`.
A smaller fashion rival retained five other categories and 60 products, but
`at_rival` returned `None`. The local model never got to see the rival.
The diagnostic before-run records this as a failure, with zero model attempts:
`/workspace/scratch/cpu-vlm-probe-2b/online-session-browse-rival-desktop-json_schema-1793000231125406912`.
This is a routing reproduction, not a claimed pre-fix CPU inference.

The generator now clears `target_category` and `target_terms` for whole-shop
browsing. It retains them for category-specific browsing. Budget, patience,
identity, arrival draws and the random stream are unchanged; purchase, compare,
gift, replenishment and bargain-hunting missions retain their existing behavior.
Product relevance scoring is unchanged: a browser without a category gets the
same general browsing score across products. No model action or thought is
rewritten, and no purchase is forced.

After the change, the same fixture enters the rival. The actual Qwen3.5-2B
Q4_K_M CPU vision model was run on the production rendered pages, five threads,
llama.cpp b11878, 8192-token context, thinking disabled, temperature/seed zero.
Artifact:
`/workspace/scratch/cpu-vlm-probe-2b/online-session-browse-rival-desktop-json_schema-1793000245840142490`.
Three real requests took 47.42 s: two choices and one exit survey, zero model
failures/fallbacks, zero application cache hits. The visit was deliberately
bounded to two steps. The first screenshot was inspected directly: it shows
the rival's hair-accessory product, five remaining category links and several
similar products. Some catalog images are placeholders; this is a rendered
simulation page, not a photograph of a real shop.

Routing/technical checks pass, but browsing quality is not claimed to pass.
The model adds the same hair clips twice; on the second choice its thought says
it will close the tab but its selected option is Add to cart. The bounded visit
ends with an abandoned cart and no order. Its survey claims no other products
were shown, contradicted by the inspected screenshot. These semantic errors
remain open, and the artifact records `goal_completed=false`.

Nine regressions cover three seeds, preservation of all other shopper fields,
equal general-product relevance, rival admission, continued exclusion for an
explicit apparel-only goal and independence of five other missions. Before the
fix, four failed and five passed in 0.74 s. The new `browse-rival` CPU probe uses
the actual sampler and rival router before running the model; it does not edit
saved user stores. Probe compilation and whitespace checks pass.

All 73 selected backend regressions pass in 15.32 s; six unrelated full-page
random-crawl cases were deselected. This selection covers sampler, arrival,
rival, rule/model session, scan and rival API behavior. Strict Pyright reports
zero errors/warnings and the backend boots. No full repository suite was rerun.

Before publication, four newer UI commits through `b4bac61d` were integrated:
layout validation details and one-based cell coordinates, starter-fill count
copy, reopening the last viewed layout, and finder keyboard navigation. The
changelog conflict was resolved by preserving both sets of entries. The project
query suspends until project data is available, so the remembered-layout logic
does not select a fallback while that initial query is pending. All 135 selected
frontend tests pass in 9.71 s. Changed-file ESLint has zero errors and five
existing compiler/refresh warnings. TypeScript and the production build pass
(20.23 s build), with bundle-size and plugin-time warnings.
