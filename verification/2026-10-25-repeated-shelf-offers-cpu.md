# Remaining CPU VLM errors on repeated shelf offers

Date: 2026-10-25. Based on main `b8ddf48c`. Actual Qwen3.5-0.8B Q4_K_M
with the F16 vision projector, CPU only, five threads, llama.cpp b11878,
8192-token context and 512 image tokens. The application schema, renderer,
prompts and offer resolver are used with live model replies and fresh caches.

Two identical Mineral Water 500ml products share a SKU and name but have
different prices. A Korean free offer competes with a 5,000-won offer; a US
one-dollar sale competes with a $50 offer. The shopper explicitly wants the
free/one-dollar offer and has zero/one dollar remaining. Each case is mirrored
left/right; badge shuffling is independent of that position.

With badges 1 then 2, the model identifies the desired price in its reason but
selects badge 1 in all four cases. Both right-hand cases therefore resolve to
the expensive offer. Its JSON, product name and badge are valid. The resolver
correctly retains that selected badge for duplicate names; this is not evidence
that it should silently substitute the cheapest offer.

Changing the badge shuffle reproduces a different failure: both free cases
match, but the left-hand $1 offer carrying badge 2 is answered as badge 1 ($50).
The other three cases match. This is why one passing image or fixed badge
assignment is insufficient verification.

Evidence under `/workspace/scratch/cpu-vlm-probe/`:

| Production fixture | Directory | Matches explicit request | Per-call seconds |
| --- | --- | --- | --- |
| Badges 1, 2 | `shelf-offers-baseline-1792966840099388716` | 2 / 4 | 6.41–7.00 |
| Badges 2, 1 | `shelf-offers-8-1792967280523578020` | 3 / 4 | 6.44–7.74 |

Each call saves the actual image, visible badge/price mapping, returned choice,
resolved price, and HTTP request/reply bodies without headers. Timings are
observations; the persistent server can reuse prefixes. Initial scratch KRW
fixtures accidentally rendered USD (`shelf-offers-1792966754916951249`); those
KRW results were discarded and the corrected baseline above was run.

Several scratch alternatives were tested and **none was shipped**:

- Appending printed price tags to the prompt still missed both right-hand
  choices (`shelf-offers-legend-1792966870345557654`).
- A joint name/price/badge choice schema without listing its labels in the
  prompt returned no product in all four cases
  (`shelf-offers-joint-1792966939776197768`). Grammar constraints alone do not
  provide the model with the choices' meaning.
- Listing those joint labels, or putting name/price ahead of the badge, fixed
  the right-hand USD example but still missed the right-hand free offer
  (`shelf-offers-joint-listed-1792966993433343519` and
  `shelf-offers-price-first-1792967065101229304`).
- Including promotion text fixed both free examples but regressed the right-hand
  USD sale to the expensive offer with zero interest. An additional no-free-offer
  case selected a paid item with positive interest
  (`shelf-offers-promo-choice-1792967141826926543`). Interest is not a purchase;
  these outcomes do not establish that the executor would spend beyond a budget.

The committed probe runs the production glance task and resolution, not a whole
shopping visit or purchase executor. It exits nonzero when the returned offer
fails the explicit fixture request or the model call fails. The selected price
is checked independently of JSON validity. Positive interest is not itself a
payment, and no user store is changed. No model output is mocked and no paid
provider is used.

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-shelf-offer-probe.py \
  --shuffle-seed 7 --output /tmp/twinstore-local-probes
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-shelf-offer-probe.py \
  --shuffle-seed 8 --output /tmp/twinstore-local-probes
```

The committed probe was executed with shuffle seed 8 and reproduced the remaining
USD error. The shopper prompts, response schema and renderer are unchanged.

## Additional setup-form experiments withheld

Removing the long template list and the sample campus name from the facts prompt
still omitted supplied hours/location. The unspecified bookshop invented a
city-center description. Four actual runs are stored as
`setup-*-facts-short-*` under the same scratch directory.

Adding the full output schema to that short prompt recovered the supplied
10–18 and 24-hour windows and the overnight warning, but still omitted the
location and read weekends as every day. More seriously, it invented everyday
10–22 opening and USD currency for the unspecified bookshop. All four full
checks failed (`setup-*-schema-prompt-*`). This schema-prompt change was withheld;
there is no global schema injection or store-facts prompt change in this cycle.

## Latest-branch integration

This cycle also integrates `70d51a3b`: the online report opens its paired store
run, large run-form store lists can be filtered, and capture/model-notice layout
updates are retained. During review, malformed optional `setup_id` metadata was
found to become a nonempty fake ID (for example null became the string "None"),
which enabled a broken navigation link. Only nonblank text IDs are now returned;
otherwise the comparison remains readable and its layout ID is empty. Six
malformed-value regressions fail before that guard.

Integration verification passed 35 backend tests, strict typing with zero errors
and warnings, backend boot, 58 focused frontend tests, TypeScript, changed-file
lint, and the frontend build (20.03 seconds; existing chunk-size warnings).
