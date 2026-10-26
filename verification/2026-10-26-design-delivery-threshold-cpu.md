# Keep AI delivery-threshold edits separate from delivery fees

On main `16740f01`, the actual CPU model handled “set the free-shipping
threshold to $50; keep the shipping fee” by setting **shipping_fee to zero**,
leaving the threshold at $35. Its reply claimed the threshold was $50 and
the $4.99 fee was unchanged. Replaying the resulting options through the
real checkout calculation for the fixture's cheapest product (Metal Bobby
Pins 40pk, $2.99) changed delivery from $4.99 to free. A zero-threshold
request likewise changed the fee while leaving the threshold untouched.

The design prompt now distinguishes the fee charged below the threshold
from the qualifying order total, with examples for positive and zero
thresholds. A combined-request example retains ordinary free-delivery plus
popup-removal behavior. The final user message repeats the concrete result
shape after the conversation: return actual updates and a reply, rather
than the JSON schema. Existing schema validation, request output limits,
retry bounds, currency conversion and checkout rules are unchanged.

The format reminder addresses a separate observed failure in plain JSON
mode. Without it, a threshold probe copied `$defs`, enum definitions and
properties until the 900-token limit, then repeated the same truncated
schema on its second attempt (108.58 seconds total). With the final prompt,
the same threshold edit returned the intended numeric update in one call.
This is not a general latency benchmark: the server could reuse prompt
prefixes throughout these runs.

The existing “mentioned but not changed” check also grouped delivery fees
and thresholds together, allowing a fee update to hide an explicit unset
threshold claim. It now tracks named thresholds separately, without also
reporting an unmentioned fee. Three new regressions failed before this
repair; an API regression verifies that the warning reaches the client even
when the fee was already at the proposed value and no design changes.
The saved store is not modified by drafting.

All runs below used Qwen3.5-2B Q4_K_M on CPU, llama.cpp b11878, five CPU
threads, no GPU, 8,192-token context, fresh application caches and zero cache
hits. Success checks compare all design options, including preserved fees
and unrelated fields. Eight supported cases pass with the final prompt:

| Case | Mode | HTTP calls | Time | Checked result |
| --- | --- | ---: | ---: | --- |
| Threshold 0 | Native JSON schema | 1 | 4.87 s | Only threshold becomes zero |
| Threshold $50 | Native JSON schema | 1 | 5.19 s | Threshold 5,000 cents; fee 499 |
| Threshold $7.25 | Native JSON schema | 1 | 5.26 s | Threshold 725 cents; fee 499 |
| Korean request, KRW 30,000 | Native JSON schema | 1 | 9.07 s | Threshold 30,000; fee 4,990 |
| Free delivery and remove popup | Native JSON schema | 1 | 7.57 s | Fee zero and popup none |
| Korean color-only request | Native JSON schema | 2 | 8.35 s | Only theme color changes |
| Threshold $50 | Plain JSON | 1 | 29.81 s | Threshold 5,000 cents; fee 499 |
| Threshold 0 | Plain JSON | 1 | 7.17 s | Only threshold becomes zero |

The color case's first response narrated the change with an empty updates
list; the existing bounded no-update retry recovered it. It was not a
first-attempt success. The final native combined case is the earlier
`design-delivery-combined-control` run; its prompt and result-format reminder
are identical to the selected final version.

**Two exploratory cases remain failing.** In plain JSON, the combined
free-delivery/popup request removes only the popup (one call, 5.50 seconds).
A frozen-parent comparison using the original `16740f01` module failed on
that same request by copying the schema twice (104.84 seconds). The final
prompt fixes the response shape but does not complete that combined request;
no success is claimed for it. An extra cardinality reminder did not fix it
and was removed.

The “charge shipping on every order, regardless of total” request cannot be
represented by the current nonnegative finite free-shipping threshold. The
final model still claims it removed that threshold while repeating the
already-current fee (one call, 8.34 seconds, no effective changes). The new
check now reports `free_shipping_threshold` as mentioned but not changed.
The unsupported policy and misleading model wording remain unresolved;
there is no invented huge-threshold workaround. Earlier explicit limitation
instructions and a clarification example did not solve it and were withheld.

Other discarded candidates included a positive-threshold example that
still changed the fee on the zero boundary, and a version that omitted the
fee from the native combined request. Passing one example was not treated
as sufficient evidence to publish those candidates.

Focused automated validation: 42 tests passed in 5.76 seconds across sparse
response validation, mention checks and the design-chat API. Two existing
LiteLLM asynchronous logging cleanup warnings remain. Strict Pyright reports
zero errors/warnings; application import/boot, probe compilation and diff
checks pass. Final prompt construction was compared directly with saved
native/JSON wire requests, including the combined control, to confirm the
published wording matches the tested version. Frontend files are unchanged.
Logs are `/workspace/scratch/design-delivery-{focused-tests,pyright,boot}.log`.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Baselines: `design-threshold-usd-control/design-threshold-usd-json_schema-1793028469676547351`,
  `design-always-free-control/design-always-free-json_schema-1793028360636281934`,
  `design-no-free-shipping-before/design-no-free-shipping-json_schema-1793028040389464351`.
- JSON schema-copy failure: `design-threshold-distinct-design-threshold-usd-json/design-threshold-usd-json-1793028790302352678`.
- Frozen-parent combined JSON failure: `design-free-popup-parent-json/design-free-popup-json-1793029629745818140`.
- Final native combined control: `design-delivery-combined-control/design-free-popup-json_schema-1793029273290003582`.
- Final zero: `design-delivery-verified-design-always-free-json_schema/design-always-free-json_schema-1793029343925916332`.
- Final USD: `design-delivery-verified-design-threshold-usd-json_schema/design-threshold-usd-json_schema-1793029351688441591`.
- Final fraction: `design-delivery-verified-design-threshold-fractional-json_schema/design-threshold-fractional-json_schema-1793029359775529380`.
- Final KRW: `design-delivery-verified-design-threshold-krw-json_schema/design-threshold-krw-json_schema-1793029368075914505`.
- Final color: `design-delivery-verified-design-color-ko-json_schema/design-color-ko-json_schema-1793029379990667335`.
- Final JSON USD: `design-delivery-verified-design-threshold-usd-json/design-threshold-usd-json-1793029391267135218`.
- Final JSON zero: `design-delivery-verified-design-always-free-json/design-always-free-json-1793029424200260630`.
- Still-failing JSON combination: `design-delivery-verified-design-free-popup-json/design-free-popup-json-1793029434547461988`.
- Still-failing unsupported policy: `design-delivery-known-unsupported/design-no-free-shipping-json_schema-1793029779808402692`.

Checkout and warning reanalyses are
`/workspace/scratch/design-threshold-checkout-reanalysis.json` and
`design-threshold-claim-reanalysis.json`; these make no HTTP requests and
are not additional model runs. The frozen-parent runner is
`/workspace/scratch/probe-design-parent.py`.
