# Customer-generation provider classification

The customer writer treated any client with `max_parallel` as local. A paid provider
with a concurrency cap therefore lost its cost estimate and could skip the existing
cost confirmation, while also receiving the smaller local-model batch size. A loopback
model without an explicit cap received the cloud batch size.

Generation pacing, estimates and confirmation metadata now use endpoint locality.
The shared timing helper respects a cloud client's lower concurrency limit; run
estimates use that same helper instead of repeating the clamp. Existing local timing,
unpriced-model behavior and warning thresholds remain in place.

- Before: **14 failed, 14 passed in 2.45 seconds**. Cases cover provider/default/LAN
  endpoints, IPv4/IPv6/localhost loopback, no cap and caps of 1, 4 and 40, cost-triggered
  choice and actual generation pacing. Provider prices and responses were faked.
- After: **112 passed in 8.51 seconds**, including generation choices, provider
  fallback, choice handoff and ensemble run estimates.
- Strict Pyright for the three changed application modules: **0 errors**.

Logs: `/workspace/scratch/generation-provider-{before,after,types}.log`.
Estimates still use the existing timed probe and price-table approximation; this
change does not add billing guarantees or make any live provider calls.
