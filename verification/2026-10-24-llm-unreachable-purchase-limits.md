# Exclude unreachable purchases before limits

A layout can be valid while its entrances serve disconnected areas. The LLM engine
kept a purchase in the other area until route execution dropped it. Before that
drop, the purchase consumed the planned-product limit and its price counted against
the budget, suppressing real reachable purchases. A 500-unit inaccessible purchase
could remove the shopper's affordable 100-unit impulse purchase, leaving no sales.

The engine's initial planned/impulse buy guard now resolves the same exact offer
used by execution and verifies a path from the shopper's starting entrance to its
unlocked, walkable face. Failed purchases are counted as invalid before product
and budget limits. Reachability is memoized per destination within the guard and
uses the existing pathfinder/cache; no model calls or retries are added. Standalone
SKU-only guard callers remain compatible. Layout data and cached model answers
are not mutated. The checkout/exit reachability checks remain in the route layer.

The pre-fix run failed 48 cases with 48 connected-layout controls passing. The
96-case matrix covers planned and impulse purchases; budget, line-count and joint
limits; both route orderings; generated codes and canonical SKUs; a closed partition
versus an open doorway; and cardinal/diagonal routing. Each layout passes validation.
Assertions check the surviving purchase, exact spend, drop attribution, one checkout
with the original 19-second dwell, exit and preservation of the source layout.

Related offer identity, exposure, budget/quantity and unreachable service-route
checks passed: 385 cases in 5.42 seconds, with one existing LiteLLM logging-cleanup
warning. Another 70 product-count controls passed in 2.81 seconds (455 unique cases
total). Strict Pyright: zero errors.
All responses were scripted; no live inference was used.
