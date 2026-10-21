# Candidate research — observed unit prices (2026-10-21)

These are source-based requirements hypotheses. No retailer interviews, customer demand study or market validation was performed. Public guidance supports the problem framing, not a claim that this feature increases sales.

## Checked sources

- ACCC, [Unit pricing](https://www.accc.gov.au/business/pricing/unit-pricing), HTTP 200 on this cycle. Unit prices next to total selling prices help compare products of different quantities. Australian regulatory context; this worksheet does not certify local legal compliance or prescribe label units.
- COS, [Preregistration](https://www.cos.io/initiatives/prereg), HTTP 200. Planning ahead distinguishes planned and unplanned research; exploratory work is legitimate but not a substitute for independent hypothesis testing.
- Shopify, [GMROI](https://www.shopify.com/blog/gmroi), HTTP 200. Inventory return relates gross margin to inventory investment. Used only as context for a possible operational cost-sampling improvement, not as evidence for universal targets or benefits.
- GS1 landing/reference URLs attempted in this cycle returned 404, as did an attempted FDA food-storage URL and Shopify retail shrinkage URL. Their content was not used as evidence.

## Compared candidates before implementation

| Candidate / users | Problem and evidence | Existing overlap / missing piece | Required data and feasibility | Verification |
|---|---|---|---|---|
| Observed competitor unit-price worksheet / marketers and store operators | Different packs and observation dates can mislead price comparisons; ACCC explains quantity normalization | Town has estimated competitor effects; product library accepts competitor packs; receipts read item prices. No normalized observed cross-retailer offer audit found | Operator-verified comparable groups, retailer/offer IDs, dates, quantity, pack count, total price, currency, stock and conditions. High feasibility without OCR/model/network calls | Exact mass/volume/count conversions, matching scope, zero denominators, stale/future/conditional offers, duplicate IDs, CSV and UI lifecycle |
| Prospective protocol and amendment ledger / researchers and professors | COS distinguishes planned from exploratory analysis | Existing simulation manifests, locked field assignments and exploratory factorial reporting; no general prospective amendment ledger | Hypotheses, estimand, stopping/exclusion rules, timing and immutable version references. Moderate feasibility; would require durable concurrency-safe storage and clear distinction from external preregistration | Immutable history, revisions, concurrent writes, late amendments and export reproduction |
| Inventory cost sampling planner / actual operators | Endpoint average inventory can misrepresent fluctuating investment; GMROI needs an appropriate cost denominator | Existing period inventory review explicitly uses opening/closing average; no irregular-date cost snapshots | Dated inventory-at-cost snapshots and boundary coverage; moderate feasibility with explicit interpolation assumptions, no fabricated missing observations | Irregular intervals, duplicate dates, partial periods, zero cost, reconciliation with endpoint method |

## Selection and integration

Choose observed unit prices: this adds external competitive pricing decisions after inventory operations and synthetic factorial research, rather than another staff-script improvement. It is deterministic and can be validated without costly models. Compare only operator-asserted comparable products, separate currencies and quantity dimensions, and retain exclusions rather than treating missing offers as zero. No confidence intervals, repeated significance tests, causal claims or employee/shift pooling are involved. Changing observation windows is exploratory descriptive filtering; a low observed price is not an optimal price or evidence of a sales effect.

Initial local/remote operator head was `6661fae6`. Fetched main `3721cbdd`, scenarios `570f1968`, edge `d5b403d8`, photoreal `dc9a7805`; integrated to `b92364f2`. One TemplatePicker conflict resolved preserving translated dimension/currency labels and shared-floor sizing controls. Existing operator results remain in ancestry. Prior parastore checkout left untouched.

Next distinct-domain candidate: prospective research protocol/amendment ledger, or dated inventory-cost snapshots if operator evidence becomes available.

Final additional integration: main `58cf0382`, scenarios `6c088615`, edge `b7f969ca` into `10a2f230`; only frontend/docs changed after the feature commit. Existing operator work is retained. See the verification record for final checks.
