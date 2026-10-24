# Keep impulse decisions at the offers actually presented

The impulse guard checked whether a SKU had been exposed, but a canonical-SKU
answer could still resolve to an unseen placement with a different price. A
short-code answer could also point to an unseen identical copy of its offer.
Consequences included detours to shelves outside the presented list and rejecting
an affordable visible item against the price of an unseen premium copy.

Impulse decoding now receives the actual exposure anchors and binds purchases
only within that set. If a provider ignores the code grammar and returns a known
canonical SKU, it selects the anchor offer presented for that SKU. An unavailable
anchor is dropped by the existing invalid-buy guard; an unseen copy cannot replace
it. Unknown/unexposed SKU guards, hidden-field stripping, planned-purchase
destinations, exposure aggregation and visibility ranking remain in place. Cached
answers are rebound after loading, so the same rule covers canonical and coded
cache entries without changing their format again.

Before the fix, 12 regressions failed and six controls passed. New coverage checks
both exposure modes and route orderings, codes versus canonical SKUs, identical
and differently priced copies, locked observed offers, actual destination/price,
and the visibility model's selected shelf level. Existing HTTP/cache tests now
also exercise canonical replies to both structured modes, including a real SKU
that resembles a code.

Focused verification covers 274 unique passing cases after updating the expected
price in the internal-hint controls: the first run passed 258 and exposed 16 old
assertions expecting the first SKU placement instead of the 900-unit offer shown
to the impulse model. Those controls now explicitly check the presented price and
its unchanged selection across every injected hint; all 60 boundary tests passed
on the final rerun. The production patch did not change between those runs.
Strict Pyright reported zero errors. Existing LiteLLM logging-cleanup warnings
occurred (ten in the focused run, seven in the boundary rerun). All responses were
scripted; no live or paid inference was used.
