# Candidate research — research protocol history (2026-10-21)

Requirements are hypotheses based on public sources and repository inspection. No interviews, market
validation or evidence of improved research/sales outcomes was collected.

## Sources checked this cycle (HTTP 200)

- COS, [Preregistration](https://www.cos.io/initiatives/prereg): writing a plan before study results helps
  distinguish planned and unplanned work; the same data should not generate and independently test a hypothesis.
- OSF, [Welcome to Registrations & Preregistrations](https://help.osf.io/article/330-welcome-to-registrations):
  registration preparation, templates and registration actions. External repositories/registration services
  provide a different publication and permanence context from an editable, self-hosted local application.
- ACCC, [Unit pricing](https://www.accc.gov.au/business/pricing/unit-pricing): quantity normalization supports
  price comparison. Australian guidance is not universal price-label compliance certification.
- Shopify, [GMROI](https://www.shopify.com/blog/gmroi): gross margin relative to average inventory investment.
  Used to motivate transparent inventory-cost denominators, not as proof of targets, ROI or causal effects.

## Candidates compared before implementation

| Candidate / primary users | Work problem and source basis | Existing overlap / gap | Data and feasibility | Validation |
|---|---|---|---|---|
| Research protocol and amendment history / marketing researchers, professors and marketers preparing studies | Separate original outcome, sample/exclusion/stopping/analysis decisions from changes made after seeing results; COS and OSF guidance | Existing manifests describe runs; field pilots lock assignment plans; factorial analysis is exploratory. No general prospective protocol/change ledger found | Explicit research plan, planned independent unit count, synthetic/observed scope and self-declared data visibility. No model calls. Moderate implementation effort due to durable writes and stale revisions | Canonical hashes, complete snapshots and field differences; idempotent create, concurrent amendments, interrupted writes, corrupted history, UI request/navigation lifecycle |
| Inventory cost snapshots / store operators | An endpoint average may miss changes in invested inventory within a period; GMROI denominator context from Shopify | Inventory review currently uses opening/closing average and clearly states that limit | Dated cost observations, period coverage and explicit interpolation assumptions. Moderate feasibility; missing dates cannot be invented | Irregular dates, duplicate snapshots, coverage gaps, zero values, weighted time intervals |
| Shelf price-label reconciliation / category marketers and operators | Compare entered label quantity/price with item data and normalized unit prices; ACCC comparison rationale | New competitor unit-price worksheet already normalizes observations; no separate shelf label versus verified product audit | Two independently verified sources and matching IDs; moderate feasibility, potentially OCR-assisted later | Pack/unit/currency mismatch, duplicates, missing match, rounding, unknown eligibility; no legal-compliance verdict |

## Selection

Choose research protocols to diversify after inventory operations, synthetic price×sign analysis and competitor
unit-price comparison. Implement a project-scoped append-only application workflow: complete original plan,
full amendment snapshots, recorded reasons, declared data stage and exact differences. Preserve the initial
plan; optimistic head hashes and a cross-process lock reject simultaneous overwrites. Export reproducible
JSON and a field-change CSV. The local history is not an external preregistration, trusted timestamp or
proof that outcomes were unseen. It does not enforce simulation execution or establish study validity.

Important design disclosures: users can edit files outside the app and recompute local hashes; a hash chain
checks internal consistency, not authenticity. Declared data stage cannot move backward within the ledger.
No p-values or simulated/observed outcome effects are calculated. Planned sample size is recorded, not a
power guarantee; the plan must explicitly address missing data, repeated analyses and staff/shift clustering.

Initial operator head `bc6e941a`; integrated fetched main/edge `138c9fd5`, scenarios `39a0b9ba` and the already
included photoreal head to `188a5b50`. Resolved one TemplatePicker merge conflict by retaining the shared
multilingual search helper rather than restoring an unused superseded local helper. Existing features and
old parastore checkout are preserved.

Next different-domain candidate: dated inventory-cost snapshots or a manually verified shelf-label audit.

Before full validation, integrated main/edge `1c908e9e` and scenarios `ac90b1d3` into `a1eb7e1b`. This preserves operator feature commit `4ac56925` and includes the latest fetched plaza formats, capture lifecycle and shopper-motion updates.
