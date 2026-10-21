# Candidate review: inventory, experiment design and research protocols

Reviewed before implementation in this cycle. These are source-informed requirements hypotheses, not
interviews with operators/professors or demonstrated market demand. Previous cycle implemented staff time;
this cycle deliberately evaluates other domains.

| User / problem | Candidate and existing gap | Data and validation | Decision |
| --- | --- | --- | --- |
| Store operator / category marketer: replenishment decisions need trustworthy period stock and margin records | Inventory movement reconciliation plus period GMROI/turnover. Existing restock priority and pack-budget modules use modeled/entered demand; no observed period inventory review exists. | One CSV row per SKU, opening/closing stock, receipts, sales/returns/adjustments, net revenue/COGS and inventory value at cost. Offline arithmetic; test reconciliation, missing fields, returns, zero denominators, precision and aggregation. | Selected: distinct operational module, no model calls or invented store data. |
| Marketing researcher / professor: distinguish intended analyses from exploratory findings | Protocol snapshots and amendment comparison for marketing studies. Run manifests/fixed field plans already exist; avoid another generic manifest exporter. | Saved hypotheses, outcomes, exclusions and plan versions. Test immutability, omitted analyses and reproducible exports. | Strong next candidate; requires protocol lifecycle design. |
| Marketer / methods teacher: price and POP effects may interact | Explicit factorial design/interaction reports atop existing paired A/B runner. Conjoint and multi-arm experiments exist but do not themselves define an interaction analysis. | Four compatible arms, complete per-shopper paired outcomes and predeclared contrasts. Test incomplete cells, seed comparability and multiple testing; synthetic-only interpretation. | Candidate for a later research-focused cycle. |

## Sources fetched and read this cycle

- [Shopify, GMROI Formula: How to Calculate It for Retail (2026)](https://www.shopify.com/blog/gmroi):
  gross profit divided by average inventory at cost. Supports a margin/inventory review, not a sales lift claim.
- [Shopify, Sell-Through Rate (2026)](https://www.shopify.com/blog/sell-through-rate): discusses both units
  received and stock available during a period as denominators. Those are not equivalent with carry-in stock
  or returns. This module therefore labels its own convention explicitly: net units sold divided by
  opening units + receipts + other inbound stock. Customer returns reduce the numerator and are not counted
  a second time in supply. No category benchmark is imported from the article.
- [Center for Open Science, Preregistration](https://www.cos.io/initiatives/prereg): analysis plans and
  transparent changes distinguish confirmatory from exploratory work; local snapshots are not public registration.
- [NIST/SEMATECH, Choosing an experimental design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3.htm):
  objectives, randomized blocks, factorial designs and confounding motivate an explicit interaction workflow.

The Shopify `/retail/` links redirect to the `/blog/` URLs above. Vendor guidance is not evidence that this
specific feature improves profit. Public sources and repository inspection, not real store data, inform selection.

## Metric contract chosen before coding

- Same explicitly selected period and currency for every CSV row; no unit/currency inference or annualization.
- Expected closing units = opening + received + customer returns + other in − gross sold − other out.
  Difference = recorded closing − expected closing. Reconciliation is an endpoint check, not proof that every
  intraperiod balance was nonnegative or that the inputs were audited.
- Gross profit = supplied net sales − supplied net COGS; COGS reversals may be negative for return-heavy periods.
- Average inventory cost = (opening value at cost + closing value at cost) / 2. This endpoint approximation can
  miss replenishment peaks; use more frequent inventory records externally when needed. It is not average retail value.
- Period GMROI = gross profit / average inventory cost; period turnover = net COGS / average inventory cost.
  Negative gross profit stays negative. Negative COGS makes turnover unavailable; it does not become zero.
- Net unit sell-through = (gross sold − customer returns) / (opening + received + other in). Negative net units
  or zero supply make it unavailable. Returned stock is represented in the balance separately.
- Stock mismatch or nonzero value attached to zero opening/closing stock withholds ratios. Zero average cost
  withholds financial ratios. Report reasons, not fabricated zero values. Portfolio financial ratios use sums
  of profit/COGS and average costs across all supplied rows, never an unweighted average of SKU ratios; do not
  silently drop unreconciled rows. Do not combine unit sell-through across SKUs with incompatible units.
- No confidence interval, causal promotion effect, staff ranking, automatic order or inventory write-back.
