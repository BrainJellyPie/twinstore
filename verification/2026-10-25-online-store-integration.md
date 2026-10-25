# Online shopping integration and order boundaries — 2026-10-25

Integrated `claude/online-shopping-features-ji7y0f` at
`584864b8acf63c3ce722f40a5b8561d32c6ea3c0` into main at
`e632e46e18c015aba3f8257851318808213aa50a`, retaining both histories.
The branch adds online store templates, simulated browser shopping, shopper
policies, comparisons, reports, replays, and the six-language online UI.
The published v0.4.14 tag and release branch remain at their tested source.

## Confirmed defects and repairs

- A product with stock 1 could be added three times and ordered with quantity 3.
  Cart additions now enforce finite stock and the existing 99-unit limit across
  listing, product, wishlist, and cart controls. Checkout revalidates stale carts,
  including sold-out, unknown, duplicate, and over-stock product rows. Existing
  cart contents remain available for correction; valid orders preserve prices.
  Stock belongs to each independent simulated visit, not a shared depletion
  counter across the comparison panel.
- Online stores created from physical layouts can use USD, KRW, or JPY. Comparing
  different currencies previously combined unconverted budgets and order totals.
  Such comparisons now return HTTP 400 before creating a job. Same-currency
  comparisons remain supported for all three currencies.

## Evidence and checks

- Existing online backend tests before repairs: **32 passed**.
- Stock regressions before repair: **27 failed, 11 passed**. Cases include stock
  0/1/2/98/99/100/unlimited, repeated additions, hidden exhausted controls,
  existing-cart Buy now, stale checkout, and exact boundary totals.
- Currency regressions before repair: **4 failed, 3 passed**. These use the real
  layout-generation and `from_store` APIs; USD/KRW and USD/JPY are checked in
  both orders, plus USD/USD, KRW/KRW, and JPY/JPY controls.
- Final targeted backend checks: **77 distinct tests passed** across the online
  integration/stock run (70) and corrected currency run (7). An earlier currency
  fixture tried to change currency through the site-edit API, which deliberately
  preserves it; that fixture was corrected before recording the baseline above.
- Full-source Pyright: **0 errors, 0 warnings**.
- Frontend: TypeScript passed; **3 online browser tests passed**; changed-file
  ESLint had no errors and one existing route-export Fast Refresh warning; Vite
  production build passed with bundle-size/plugin timing warnings.
- No paid model requests or native model inference were used. These checks cover
  the integrated code and deterministic boundaries, not model-output accuracy.
  The full backend suite was not repeated locally.
