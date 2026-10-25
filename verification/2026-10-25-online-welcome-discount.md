# Online welcome-offer consistency — 2026-10-25

Changing a newsletter or coupon popup's discount to zero still advertised 10%
off, but accepting it applied no discount. Rule shoppers also received the
discount acceptance bonus and narrated taking a discount. Coupon popups with
an empty code invented WELCOME, although checkout had no such configured code.

Welcome copy now uses the configured percentage. Zero-percent newsletters
offer updates; zero-percent coupon popups remain a plain welcome, preserving
the configured popup friction. A positive offer without a code describes the
discount applied on acceptance. Rule shoppers retain the existing base
acceptance chance without the nonexistent discount bonus or narrative.

Baseline: 32 failed and 22 passed in 3.14s. The regressions cover 0/5/90 percent,
USD/KRW/JPY, both popup kinds and present/absent codes, with independently
calculated checkout totals. Sixteen intercepted real SDK cases cover native
Ollama and OpenAI-compatible local servers in JSON and JSON-schema modes,
checking the actual model prompt, valid actions and cache reuse. Rule tests
cover accepting and declining without an incentive.

Final focused verification: 116 passed in 20.25s, including existing online
store, ad, reminder and coupon paths. Full backend source Pyright reported zero
errors/warnings; server boot passed. Fifteen existing LiteLLM async logging
cleanup warnings occurred. No live model calls or frontend changes.

Separate exploratory layout probes covered 1,400 deterministic combinations
over 82 formats, floor sizes, styles, aisle directions, entrances/exits,
checkouts, reserved areas and seating. All 1,027 generated stores passed
geometry/accessibility validation; 373 impossible arrangements returned
descriptive ValueErrors. The two probes took 3.16s and 3.80s. They use generated
catalog products, not live model answers.
