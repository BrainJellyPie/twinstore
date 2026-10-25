# CPU online choices: action labels are not a general fix

Date: 2026-10-25. Qwen3.5-0.8B Q4 on the persistent CPU server, with fresh
application caches and actual rendered pages. Based on main `35aed468`.

A purchase shopper on the fashion home page wanted to find Travel Shoe Care
Tin Empty through search. The numeric-choice policy selected Baseball Cap
instead, on both desktop and mobile. Its descriptions referred to different
products. The desired product was also available as option 24; the model chose
option 23. There was no response-format error or rule fallback.

An explicitly worded search request using the text-view policy did not solve
this: it selected the home logo and invented a 15-minute wait, although the
shopper had just arrived. This is a remaining semantic failure, not evidence of
a missing search-text field or an inaccessible search control.

A scratch experiment changed the wire choice from a number to an exact action
label followed by its number, while mapping it back to the same internal action.
Both desktop and mobile then searched for the exact target. However, the mobile
thought still described clicking a product rather than searching. More seriously,
on the existing checkout fixture a $1-budget browse shopper selected the $19.99
place-order action. The earlier numeric policy avoided that order.

**The label-choice schema and prompt experiment was not shipped.** A successful
search example does not justify a change that fails another major boundary.
The production online choice schema and prompt remain unchanged. These results
also show why a valid JSON reply and `source: model` do not establish a correct
decision.

Evidence under `/workspace/scratch/cpu-vlm-probe/`:

| Fixture | Result directory | Calls | Seconds |
| --- | --- | ---: | ---: |
| Numeric desktop search | `search-desktop-1792963363126456797` | 1 | 10.66 |
| Numeric mobile search | `search-mobile-1792963412704799371` | 1 | 9.16 |
| Explicit search, text view | `search-desktop-1792963438794423353` | 1 | 6.34 |
| Label desktop search | `search-labels-desktop-1792963500813215755` | 1 | 9.95 |
| Label mobile search | `search-labels-mobile-1792963558845540942` | 1 | 8.92 |
| Label checkout | `checkout-labels-1792963571221930112` | 1 | 7.35 |

Scratch probes: `search_probe.py`, `search_labels_probe.py` and
`checkout_labels_probe.py`. Screenshots, shoppers, sites and raw request/reply
bodies without credentials are retained with each result. No paid calls or saved
user-store edits occurred. Timings are observations, not benchmarks.

This cycle integrates the separate upstream mobile tab/download-button fix
(`6744cf78`, including `5af9da84`), preserving the current backend fixes and
research-note removal. It does not claim to repair the online semantic failures.

Integration checks passed: 35 frontend tests, TypeScript checking, changed-file
lint with no errors or warnings, and the frontend build (19.61 seconds).
Backend application source is unchanged in this cycle.
