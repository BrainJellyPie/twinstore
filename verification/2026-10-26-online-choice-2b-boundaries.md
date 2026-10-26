# Online choices: actual 2B CPU experiments and retained failures

2026-10-26, from main `da28b910`. Qwen3.5-2B Q4_K_M with its F16 vision
projector, llama.cpp b11878, five CPU threads, 8192-token context, temperature
and seed zero, thinking disabled. These use actual production rendered pages,
model calls and session transitions. Each has a fresh application cache; the
server is warm. All artifacts below are under
`/workspace/scratch/cpu-vlm-probe-2b/`.

The previous numeric-choice baseline repeatedly added a product while its
thought said it would leave. Two scratch wire/prompt variants were compared.
Neither changes production prompts, schemas or actions in this commit. The
same strategies had previously failed on the 0.8B model; these are explicit
2B comparisons, not newly discovered strategies.

| Variant and artifact | HTTP calls | Seconds | Finding |
| --- | ---: | ---: | --- |
| Thought before option, checkout / `browse-budget-thought-first-desktop-json_schema-1793001137931133414` | 1 | 17.34 | Chooses Apply coupon instead of immediately placing the $19.99 order with a $1 budget. Its thought falsely claims 15 minutes on site; elapsed time supplied was one minute. Passing the narrow no-order check is not a full semantic pass. |
| Thought first, two-step broad browse / `online-session-thought-first-browse-rival-desktop-json_schema-1793001170476647091` | 3 | 48.47 | Searches for clips and opens a product, rather than adding the same item twice. Thoughts are clipped and describe an action not yet taken. The artificial two-step bound is reached; no goal-completion claim. |
| Thought first, six-step purchase / `online-session-thought-first-purchase-desktop-json_schema-1793001387905027472` | 7 | 134.03 | Asked to buy one Cotton T-Shirt, adds a Linen Shirt instead and wanders between cart and home. No order. The survey invents removal/re-adding and a missing “Buy exactly one” button. |
| Full numbered option label, purchase / `online-session-labelled-options-purchase-desktop-json_schema-1793001548714434298` | 6 | 111.87 | Opens the correct T-shirt, adds it three times, then leaves. The third choice still says “close the tab” while selecting Add to cart. Cart is $59.97 against a $50 limit; survey incorrectly says $39.97. |

The labelled variant maps only an exact, model-selected option label to its
original number. It never infers an action from thought text. The final visit
leaves naturally after five choices (maximum six), with a sixth HTTP request
for the survey. Other sessions use their stated two/six-step bounds. All visits
produce parseable model choices and surveys without rule fallbacks, yet their
purchase goals fail. Technical validity is kept separate from goal completion
and the manual content review. No fabricated action, forced purchase or budget
rewrite is used to make a test pass.

The labelled run's second image was inspected directly: a readable Cotton
T-Shirt page with $19.99, the Add to cart badge 21, cart badge 5 and close-tab
badge 23. “Best seller” badges are on similar Linen Shirt/Baseball Cap tiles,
not the target T-shirt as its first thought claims. The image is a generated
shop page with product images, not a photograph of a real shop.

## Request evidence survives failed connections

`verification/local-online-session-probe.py` previously wrote the request and
its screenshots only after HTTP returned. A timeout/disconnection erased the
input needed to reproduce that failure. It now writes `requests.jsonl` and
separate image files before awaiting the response, counts attempted and
completed calls separately, and links responses to their attempts. It saves
no headers and replaces inline image bytes with their saved filenames.

A refused loopback-port control, not a model inference, verifies the failure
path: `/workspace/scratch/online-request-failure/online-session-purchase-desktop-json_schema-1793001502719932764`.
It records two attempts, zero completed HTTP calls, the actual rendered input
image, one rule fallback and no survey, and correctly exits with failure in
1.43 seconds. The six-call labelled experiment exercises successful recording
with six attempts/completions and zero application cache hits. Python
compilation and whitespace checks pass.

## Integration

Integrated upstream `8817f409`: permit deleting a top-level layout when
another layout remains, expose reviewed deletion in the store panel, and keep
the existing tree/layout locks and running-layout protection. The changelog
conflict was resolved by retaining both sides. No production model behavior
is changed by this integration.

The 73 selected backend cases pass in 13.97 seconds, covering deletion,
concurrent saves/run starts, responsive lock waits and reviewed draft saves.
All 22 selected frontend cases pass in 3.53 seconds. Strict backend Pyright
reports zero errors/warnings and the backend boots. Changed-source frontend
ESLint has zero errors/warnings. TypeScript and the production build pass
(20.23 seconds), with the usual chunk-size and plugin-time warnings. No full
repository suite was rerun.
