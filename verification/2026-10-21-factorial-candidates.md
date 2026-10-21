# Candidate review: experiment interactions, protocols and competitive pricing

Reviewed before implementation. Requirements below are public-source hypotheses, not operator interviews,
professor feedback, market validation or evidence that the feature improves sales. Previous cycle shipped
observed inventory review; this cycle selects a distinct research/marketing workflow.

| User / work problem | Candidate / repository gap | Data, feasibility and validation | Decision |
| --- | --- | --- | --- |
| Marketer / research methods professor: a price change and a promotion sign may behave differently together | Paired 2×2 price × sign contrasts. Existing A/B reports compare each arm with control but do not compute the interaction, and save only aggregates. | Preserve minimal per-shopper outcomes during future A/B runs; use existing runner, no extra model calls. Validate exact single-factor/combined changes, common four-cell cohort, missingness, known contrasts, paired resampling and stale exports. | Selected: connected extension of actual experiments; different from inventory and staff scripts. |
| Marketing researcher: distinguish planned and exploratory analyses | Protocol snapshots and amendment comparison. Existing manifests and fixed field plans are not a general protocol history. | Requires prospective lifecycle, immutable versions and study linking. Test retrospective labels, concurrent amendments and complete change exports. | Next research candidate; avoid duplicating basic manifests. |
| Store operator / category marketer: compare different pack sizes fairly | Competitor unit-price worksheet. Existing town competitor events do not normalize pack quantities/currencies. | Operator-verified pack size, unit, price/date/currency; no automatic scraping or inferred competitive response. Test unit conversion, incompatible units, promotions and stale prices. | Next operational candidate; distinguish measurement from compliance advice. |

## Public evidence checked this cycle

- [Center for Open Science: Preregistration](https://www.cos.io/initiatives/prereg) distinguishes planned,
  data-independent research from unplanned exploratory work and asks authors to disclose changes. The selected
  analysis is explicitly exploratory because users choose arms/outcomes after results exist; no claim of preregistration.
- [SciPy bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
  describes paired index resampling and percentile intervals, and notes limitations of the percentile method.
  This module uses NumPy, not a new SciPy dependency: fixed-seed paired percentile intervals are approximate
  panel-resampling summaries, not uncertainty about model validity or real-store effects.
- [Australian Competition and Consumer Commission: Unit pricing](https://www.accc.gov.au/business/pricing/unit-pricing)
  explains how unit prices enable comparisons across quantities. This supports the competing candidate's
  measurement problem; Australian requirements are not generalized into worldwide compliance claims.

NIST design pages and Wikipedia factorial/Bonferroni pages returned HTTP 403, PSU's factorial lesson returned
503, and the attempted GOV.UK unit-pricing URL returned 404. They were not treated as successfully read sources
in this cycle. Prior candidate documents cite NIST material fetched in earlier cycles. Factorial formulas below
are specified algebraically and verified against hand-calculated examples.

## Contract selected before coding

- Control (00), price-only (10), sign-only (01), both (11), on the same SKU. Single factors must be exactly one
  price/discount change and one promo change; the combined arm must contain exactly those two changes. Reject
  no-op stores, application warnings, duplicated identities and unsupported additional manipulations.
- For each complete shopper: price effect = ((10−00)+(11−01))/2; sign effect = ((01−00)+(11−10))/2;
  interaction = 11−10−01+00. Interaction is the difference between the conditional price effects, not their half.
- One selected whole-basket outcome: spend in minor units, units, or purchase indicator (including free purchases).
  All cell means and contrasts use the same four-cell cohort. No joining aggregates or inventing missing outcomes.
- Retain planned sampled IDs and per-arm availability before intersection. Estimates may use complete cases,
  but intervals require all sampled shoppers in all four selected cells and at least 30 shoppers.
- Resample whole shoppers with a fixed seed in bounded batches. For the three contrasts, use Bonferroni
  percentile tails at 0.05/(2×3) and 1−0.05/(2×3): nominal approximate 95% family coverage under bootstrap
  assumptions. This does not correct repeated arm/outcome selection or comparisons across experiments. No p-values,
  winner declaration, real-sales forecast or daily-traffic multiplication.
- Snapshot hashes bind review/export to exact stored source. Legacy runs without raw outcomes stay unavailable;
  never reconstruct pairs from aggregate reports. CSV includes raw selected cells, excluded IDs, formulas,
  source metadata and results. New runs retain only synthetic IDs and minimal numeric outcomes, not extra narratives.
