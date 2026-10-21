# Candidate review: observed shelf / checkout price checks

Date: 2026-10-21. These are document-based requirements hypotheses, not user interviews, market validation or measured benefits.

## Sources checked in this cycle

- [ACCC: Price displays](https://www.accc.gov.au/consumers/pricing/price-displays), HTTP 200: explicitly discusses checkout prices that differ from displayed prices, and misleading price presentation. Australian guidance establishes a practical discrepancy problem; this module does not issue legal compliance or refund decisions in any jurisdiction.
- [Shopify: GMROI](https://www.shopify.com/blog/gmroi), HTTP 200: gross profit divided by average inventory at cost. Supports careful denominator selection; vendor benchmarks and claimed outcomes are not adopted.
- [COS: Preregistration](https://www.cos.io/initiatives/prereg), HTTP 200: distinguishes planned from unplanned and data-independent from data-informed analyses. Supports provenance and explicit analysis scope, not a claim that local files are preregistration.
- NIST price-verification page returned HTTP 403. Its contents were not used and the worksheet does not implement a NIST sampling standard.

## Different-domain candidates

| Candidate / users | Problem and evidence | Existing capability / gap | Required data and feasibility | Validation |
| --- | --- | --- | --- | --- |
| Shelf versus checkout reconciliation / store operators, category marketers | ACCC describes displayed/charged price mismatches; operators need actionable exceptions before changing prices | Unit prices compares normalized competitor offers; receipt review corrects OCR; shelf audits compare placement. No paired, independently supplied display/checkout price review found | Two manually checked CSV sources with check ID, SKU, package reference, date, currency, complete item price and eligibility. High feasibility, no model calls | Exact joins, missing side, duplicate check IDs, mismatched SKU/package/date/currency, conditional terms, integer minor-unit arithmetic, source-bound export |
| Dated inventory-cost sampling / operators, retail finance marketers | GMROI depends on average investment; endpoints can miss within-period movement | Inventory review deliberately uses endpoint average; dated observations are absent | Dated inventory-at-cost observations with boundary coverage and explicit interval assumptions; moderate feasibility | Irregular spacing, no invented missing cost, zero denominators, weighted intervals and period boundaries |
| Planned versus executed study linkage / professors, marketing researchers | COS distinction between planned and exploratory work | Protocol history and run manifests now exist but are separate | Explicit run-to-protocol linkage and immutable execution metadata; moderate feasibility | Missing outcomes, amendments after data visibility, stale protocol heads, distinction between association and compliance |

## Selection and scope

Select shelf / checkout reconciliation to diversify from the just-completed protocol module into observed store operations. It is separate from competitor unit-price shopping and from stock accounting. A researcher can retain reproducible observation exclusions, but the result is descriptive: no p-value, repeated-testing claim, representative population rate, staff/shift ranking or causal sales effect.

Two sources are joined by an operator-assigned check ID within one declared store and audit date. This ID denotes one check, not a customer or a unique SKU. Repeated SKU checks are allowed and must not be treated as independent samples. Both sides must assert the same SKU, full package reference, date, currency and public terms before subtraction. Missing or ineligible observations remain visible. No fuzzy matching or currency conversion. Prices are full payable item/package prices in integer currency minor units with consistent tax/deposit treatment; no baskets, weighted goods, coupon/member/multibuy arithmetic or refunds.

All input IDs are supplied assertions, not verified evidence. Same-date checks can still differ in time/channel; operators must verify the match. The UI and export expose the basis and exclusions. No saved mutable state, automated price correction or legal decision. A combined digest binds both source byte streams and the scope for export. Keep original files; the digest does not authenticate observations.

Repository inspected at operator 198e770e; initial integration includes main a6cbebf8, scenarios 53a064f7 and edge-case fixes 7f47fe2e. Existing inventory, offers, protocols, staff pilots, receipt and shelf modules preserved. Next distinct-domain candidate: dated inventory-cost observations, then protocol-to-run linkage.
