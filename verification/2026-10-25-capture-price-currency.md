# Keep foreign shelf-tag prices out of exact store prices

The shelf-label reader preserved printed currency marks, but conversion ignored
which currency they named. A `₩1,800` tag in a USD capture became 180,000 cents
($1,800), and `$2.49` in a KRW capture became 2 won. Both were marked as exact
read prices. A separate numeric model guess could also override the conflict.

Before numeric conversion, compare recognized currency codes and the existing
dollar, euro, pound, yen and won marks against the store currency. Conflicts
return the existing unreadable-price result. Capture retains the product,
original tag text and catalog estimate with `price_estimated: true`; it does
not convert currencies or discard the shelf. The prompt now explicitly asks
the model to preserve printed currency marks and not convert the amount.

The comparison covers the app's USD/KRW/JPY formats, its zero-decimal currency
conventions, EUR/GBP/CHF/INR/CNY and common dollar currencies. This is not a new
complete ISO currency registry. Unknown currency formats retain the previous
parser behavior. Unqualified dollar and yen signs remain compatible with
recognized currencies sharing those symbols; an explicit conflicting code
still makes the amount unreadable. This check also runs on cached labels.

The new regression suite covers 21 conflicting tags with absent and two numeric
guesses, 15 matching/shared/unmarked controls and 16 real LiteLLM/Instructor
HTTP capture cases across both structured modes. HTTP cases verify product
preservation, estimated prices, an unaffected neighboring product and cache
reuse. Before the fix, 77 checks failed and 17 passed in 2.28 seconds.

The focused price, capture and optional-metadata suite passed 881 tests in
7.65 seconds; one native Grounding DINO test was skipped. Full source Pyright
reported zero errors and warnings. The 16 test warnings were existing LiteLLM
async logging cleanup warnings. No native inference, model downloads or paid
requests ran; scripted HTTP replies exercise parsing, conversion and caching,
not a model's ability to read a real photograph.
