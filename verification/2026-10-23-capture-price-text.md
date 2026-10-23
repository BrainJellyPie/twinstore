# Captured price text and currency units

Price parsing used a narrower zero-decimal set than the app's display/prompt rules,
inflating VND, IDR, CLP, ISK, HUF and TWD amounts by 100 when no useful catalog guess
was available. It also removed separators before validating them: `2.49 3.99` became
249399 USD cents, malformed mixed separators raised `ValueError`, and negative or
percentage labels could become positive prices. One such exception failed a whole
otherwise recognized shelf.

The parser now accepts a single amount with complete western/Indian grouping,
decimal commas/points, leading decimals, fullwidth forms, spaces and apostrophes.
Ambiguous numeric tags are unreadable even if the model also guessed a positive
number. The existing pipeline then marks its catalog fallback as an estimated price
and keeps other recognized products.

The capture currency set now matches the app's established unit conventions.
Explicit currency/major-unit marks and cent labels take precedence over catalog
heuristics: `$249` stays 24900 cents even beside a cheap typical product, and `249¢`
stays 249 cents. Contradictory units and sub-minor explicit prices are unreadable.
Unmarked `249` and the existing Korean/Japanese thousand-unit shorthand retain their
prior disambiguation behavior. These rules do not perform exchange-rate conversion.

Focused local validation:

- First baseline: 26 failures and ten passes in 0.66 seconds.
- Explicit-unit follow-up baseline: 12 failures and four passes in 0.56 seconds.
- Final: 752 passes and one optional GroundingDINO test skipped in 4.39 seconds.
  That test needs the capture extra and a roughly 700 MB model download; no provider
  or model downloads were needed for these regressions.
- The tests include 650 generated display/read round trips across ten currencies
  (seed 261023227), valid localized formats, ambiguous text with/without numeric
  guesses, and multi-product capture fallback behavior.
- Strict Pyright for both changed engine modules: zero errors or warnings.
