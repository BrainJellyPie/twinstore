# Integrate cart reminders and preserve better coupons

Merged `claude/online-shopping-features-ji7y0f` at
`df5f34b2df8581c534191847b18cfdb83449cc0f`, including the cart-reminder simulation,
return-visit replay markers, recovery metrics and quick experiments. Existing
survey-cutoff recovery and separate ad-campaign identity remain intact. The
reminder is simulated inside a shopper session; this integration does not send
real messages or publish another release.

Review found that a 10% reminder discount hid the control for an unused 20%
coupon. Cart, one-page checkout and multi-step review now offer a coupon when it
has not been applied and improves the reminder discount. Applied coupons whose
minor-unit discount rounds to zero are no longer offered repeatedly.

Before repair, the new boundary tests had 8 failures and 15 passing controls.
They cover greater/equal/lower discounts, no reminder, zero coupon, already-used
coupons, rounding, and text/vision model selection of the visible coupon control.

The merged source passed 465 online backend tests in 57.84 seconds (31 existing
LiteLLM asynchronous logging warnings), full-source Pyright with zero errors or
warnings, and backend boot. Frontend online and catalog tests: 83 passed in 14.54
seconds. TypeScript and production build passed (build 18.18 seconds). Changed
frontend files passed ESLint with zero warnings. Full frontend lint found zero
errors and 20 existing warnings in unrelated unchanged files; the additional
zero-warning threshold therefore failed for that full-tree invocation.
No paid inference, model downloads or full repository test rerun was needed.
