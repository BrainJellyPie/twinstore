# Physical visits on the actual 2B CPU VLM

2026-10-26, based on main `0d413856`. Qwen3.5-2B Q4_K_M with the F16 vision projector, llama.cpp b11878, five CPU threads, 8192-token context, temperature/seed zero and thinking disabled. Production entrance planning, shelf images, movement, checkout and shared stock run together. No purchase decisions or model replies are mocked. These synthetic fixtures are not an accuracy estimate for all shoppers.

Each run uses a fresh application cache and the warm server at `http://127.0.0.1:8082/v1`. Raw inputs, images, model replies, plans and receipts are under `/workspace/scratch/cpu-vlm-probe-2b/`. A zero application cache-hit count does not imply a cold inference server.

| Production fixture / artifact | Calls | Seconds | Planned lines | Units before stock / sold / lost | Outcome |
| --- | ---: | ---: | ---: | --- | --- |
| `visit-stock-one-json_schema-1793001954375134600` | 4 | 36.92 | 2 | 2 / 1 / 1 | Pass |
| `visit-unavailable-json_schema-1793002030448500125` | 1 | 11.30 | 1 | 1 / 1 / 0 | P1: unexpected planned purchase; P1: entered despite unavailable-only intent |
| `visit-free-same-sku-json_schema-1793002044326946858` | 2 | 29.96 | 1 | 1 / 1 / 0 | Pass |
| `visit-same-sku-json_schema-1793002076692974296` | 2 | 29.45 | 1 | 1 / 1 / 0 | Pass |
| `visit-browse-json_schema-1793002419776913079` | 1 | 10.91 | 1 | 1 / 1 / 0 | P1: unexpected planned purchase |
| `visit-plan-disabled-json_schema-1793002432947864637` | 2 | 30.13 | 0 | 1 / 1 / 0 | Pass |

The two stock competitors each plan one $1 bottle. Shared stock sells exactly one and records one lost unit. The free/paid copies share a SKU, but receipts retain the selected free offer (zero KRW revenue) and the affordable $1 offer instead of the 5,000-won/$50 alternative. The zero planning-cap case retains an empty entrance list while permitting the subsequent impulse purchase, as configured.

The free/paid shelf image was inspected directly: it has two Mineral Water 500ml text cards at level 3, badge 1 priced 0원 and badge 2 priced 5,000원. It is a synthetic rendered shelf, not a real-world photograph. Valid transaction invariants do not establish correct shopping intent.

Both no-purchase cases fail semantically. The laptop-only customer buys water, explaining “Need water for laptop cooling.” Its supplied prompt explicitly excludes food and drinks. The browse-only shopper also plans and buys water although shelf glances were disabled for both fixtures. This is an entrance decision failure, not an impulse purchase or a missing input. Nothing rewrites those decisions to make the checks pass.

The initial stock control used an uncommitted copy of the existing probe with only its loopback endpoint changed from 8081 to 8082. The reusable probe now accepts `--endpoint`, rejects non-HTTP/non-loopback endpoints, records that address, and saves every request and image before awaiting HTTP. Attempted and completed counts remain separate; headers and inline image bytes are omitted from the trace. The other five controls execute that updated probe.

## Withheld comparisons

Making mission, enter, items and reason required on the wire still buys water for the unavailable-only and browse-only customers. The free case passes. These actual 2B runs retain the original system/user prompts and only alter the experimental schema:

- `visit-required-mission-unavailable-json_schema-1793002307862011217`: one call, 11.90 seconds, fail.
- `visit-required-mission-browse-json_schema-1793002322262884538`: one call, 11.64 seconds, fail.
- `visit-required-mission-free-json_schema-1793002336439747755`: two calls, 30.55 seconds, pass.

The schema experiment remains in scratch only. Production entry schemas and prompts are unchanged. A similar strategy previously failed with the 0.8B model; this is a comparison using the actual 2B model, not a newly proposed technique.

Disabling only the existing entrance-map option (`entrance_image=False`), while
retaining real shelf images, prevents the unrelated water purchase but sends
the browse-only customer away. This is not shipped as a default change:

- `visit-text-entry-unavailable-json_schema-1793002490817684357`: one call,
  4.06 seconds, correct walk-out and no purchases.
- `visit-text-entry-browse-json_schema-1793002497338874261`: one call,
  2.36 seconds, incorrectly refuses the browsing visit.
- `visit-text-entry-stock-one-json_schema-1793002502239716393`: four calls,
  26.15 seconds, correct two plans and shared-stock outcome.

Sending the image before the same user text, with images still enabled, is a
separate scratch comparison. It also fails the two non-purchase decisions:

- `visit-image-first-unavailable-json_schema-1793002661467762771`: one call,
  12.97 seconds, enters and writes a purchase plan; no product is bought after
  resolution. Zero revenue alone would conceal the wrong entry/plan.
- `visit-image-first-browse-json_schema-1793002676776989806`: one call,
  9.89 seconds, turns the browser away.
- `visit-image-first-stock-one-json_schema-1793002689026280884`: four calls,
  35.29 seconds, correct stock competition.

No production image order or cache behavior is changed. The revised diagnostic
also passed a refused-port tracing control:
`/workspace/scratch/physical-request-failure/visit-unavailable-json_schema-1793002707716606069`
retains both attempted requests and input images, zero completed HTTP calls,
zero completed visits and a failed overall result (0.24 seconds). This is an
unreachable-server control, not a model result.

Appending explicit instructions distinguishing browsing from buying and forbidding
invented substitute needs also failed both controls with images enabled:
`visit-intent-clarified-unavailable-json_schema-1793002795031265735` (one call,
13.06 seconds) and `visit-intent-clarified-browse-json_schema-1793002810596507324`
(one call, 11.56 seconds). Both still plan and buy water. These prompt edits
remain scratch experiments; they are not part of the application changes.

Integration and verification for this loop are recorded in
[package label order](2026-10-26-package-label-order-cpu.md). The production
package-candidate repair there is separate from these unchanged physical
shopper prompts and configurations.

The final probe also marks `model_ok=false` when any entrance decision is
missing; previously the empty plan log passed that isolated subcheck despite
an overall failed run. Refused-port control `/workspace/scratch/physical-request-failure-final/visit-unavailable-json_schema-1793003740117372123`
confirms two attempts, zero responses/visits, preserved images and explicit
missing-decision failure in 0.18 seconds. No real model was called.
