# User needs and candidate review — 2026-10-21

These are source-informed product hypotheses, not user interviews, measured demand or proof of sales impact.
The user's latest clarification requires a broad candidate review each cycle: marketers, professional marketing
researchers, professors and store operators. Do not keep expanding employee-script features by default.

## Sources actually read

- [Shopify: Retail Metrics: 16 Key Metrics for Your Store (2026)](https://www.shopify.com/blog/retail-metrics)
  groups retail measures into money, efficiency, people and results. It includes inventory turnover,
  sell-through, GMROI, sales per employee, conversion and basket size. This is vendor guidance, not independent
  evidence of a particular feature's ROI. The original `/retail/retail-metrics` URL redirects to this page.
- [Center for Open Science: Preregistration](https://www.cos.io/initiatives/prereg)
  distinguishes confirmatory and exploratory work, recommends planning before data collection/analysis,
  reporting planned results and transparently recording changes. This supports protocol/audit capabilities;
  a local TwinStore snapshot would not by itself constitute a public OSF registration.
- [NIST/SEMATECH: Choosing an experimental design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3.htm)
  covers objectives, process variables, randomized blocks, full/fractional factorial designs and confounding.
  It provides methodological guidance; it does not validate synthetic consumers as human demand.

A Qualtrics conjoint overview URL returned HTTP 404 and was not used as evidence.

## Different candidate areas

| User | Problem and candidate | Existing support / remaining gap | Inputs, feasibility and validation |
| --- | --- | --- | --- |
| Store operator / category marketer | Reconcile inventory movement and actual sell-through/GMROI before choosing replenishment | Restock priorities and whole-pack budget plans exist. They do not establish actual average inventory at cost or realized sell-through. | Dated stock/receipt/sales/return/cost records; explicit period and valuation rules. Deterministic CSV reconciliation is feasible. Validate negative net sales, zero average stock, restocks, returns, transfers, duplicate SKUs and inconsistent snapshots. Strong next candidate outside staff scripts. |
| Marketing researcher / professor | Freeze analysis intentions and inspect deviations in synthetic marketing studies | Run manifests and fixed field designs already exist; inspect whether a cross-study hypothesis/primary-outcome/exclusion/amendment workflow is missing before implementing. | Existing request snapshots and hashes plus explicit analyst protocol. Verify immutability, revisions, omitted planned outcomes, separation of exploratory additions and export reproducibility. Do not duplicate existing manifests or claim external preregistration. |
| Marketer / research methods teacher | Factorial promotion comparison: price × sign, including interactions | Paired multi-arm marketing tests and conjoint exist; do not add a duplicate test runner. Evaluate an explicit factorial design and interaction report on top of compatible results. | Same seeded shoppers, four compatible arms and per-shopper outcomes. Check missing cells, paired completeness, interactions versus main effects, multiple comparisons and synthetic-only interpretation. Higher analysis-design scope than a small maintenance feature. |
| Operator / field researcher | Audit actual staff-time measurements before using labor-cost assumptions | Locked randomized pilot assignments and conditional cost scenarios exist, but previously no exact assignment-to-time CSV review. | Anonymous assignment IDs and observed active staff seconds; offline computation. Validate missing/duplicate/foreign rows, unequal block sizes, refusals, revision mismatch, numeric limits and export source identity. Implemented in this migration cycle. |

## Selection and rotation

Staff time review was already underway when the user clarified the broad research requirement; it is completed
here because it fills a specific evidence gap in the newly migrated cost module and can be tested without model
spend or invented store data. The migration also preserves the prior sensitivity and cost modules absent from
new `twinstore/main`. The next cycle should prioritize another domain after checking fresh code and sources,
starting with inventory movement / sell-through / GMROI or research protocol deviations. These are candidates,
not claims that those modules have been implemented or validated with stores.
