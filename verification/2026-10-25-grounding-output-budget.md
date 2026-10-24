# Separate whole-photo grounding from single-product output limits

Capture used one client configured for 320 output tokens for both identifying
one cropped product and locating up to 80 product facings in a whole photo.
Ordinary coordinate lists exceeded that limit, were truncated twice, and lost
all vision detections through the classic fallback.

Give the grounding call a per-request ceiling of 6,144 tokens. Keep the shared
client and product labeler at 320. The existing client includes per-call output
limits in cache identity, supports server-reported remaining-context adjustment,
and retains the grounding call's two-attempt limit. This is a ceiling; shorter
responses still stop at their normal end.

Measured with the existing Qwen3.5 tokenizer, the fixture's compact/indented
coordinate JSON requires these token counts:

| Facings | Integer 0–1000 | Fractions | Pixel decimals |
| --- | --- | --- | --- |
| 12 | 247 / 532 | 411 / 696 | 378 / 663 |
| 80 | 1,727 / 3,576 | 2,723 / 4,572 | 2,597 / 4,446 |

Tokenizer SHA-256: `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`.
These are measured fixtures, not a guarantee that every possible model response
or image fits every server's context window.

Before the fix, 22 HTTP cases truncated and two small compact controls passed in
3.47 seconds. The scripted server applies the measured output requirement to
the actual request limit; no inference runs. Tests use capture's client-config
factory, both JSON modes, actual LiteLLM/Instructor parsing and caching. All
coordinates must survive, the second grounding call must hit cache, and the
subsequent product-label request must still send 320 tokens.

The broader focused run passed 188 checks, with four pixel-fixture geometry
errors: their y coordinates were scaled to image width instead of height. After
correcting those fixture coordinates, all 24 budget cases passed in 3.46 seconds,
giving 192 distinct passing checks. One optional native GroundingDINO test stayed
skipped; 41 existing LiteLLM cleanup warnings occurred in the broader run. Full
source Pyright reported zero errors and warnings. No native model, downloads or
paid requests were used.
