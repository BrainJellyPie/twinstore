# Preserve currency evidence and reject ambiguous letter prices

## Reproduction and final behavior

Before this change, `฿100`, `₽100`, and several other currency signs could be
ignored by the unmarked-price heuristic, yielding an exact USD price of 100
cents. In a matching THB or RUB store, the same heuristic could reduce the
printed 100 major units to 100 minor units. Unknown store currencies also
bypassed foreign-symbol checks. Unknown Unicode currency signs could be
erased by compatibility normalization, including the rial presentation form.

The currency map now recognizes THB, RUB, TRY, PHP, ILS, UAH and NGN. Matching
signs retain literal major units; conflicting signs/codes use the existing
estimated-price path. Unresolved Unicode currency signs are checked before
normalization. An unknown store currency cannot adopt another currency's
known symbol. A lone Latin letter beside an otherwise unqualified amount
(e.g. `B100`, `P100`) is insufficient evidence of a selling price. Known units,
including dong abbreviations and explicit cents, retain their existing rules.
The pipeline keeps the product identity, raw tag and uncertainty flag; placement
preserves an existing product price instead of overwriting it with an estimate.

The separate price transcription prompt now explicitly includes currency
symbols and their strokes. Its final wording supplies no specific currency
examples. The wire schema and combined-reading prompt are unchanged.

## Real CPU observations

Qwen3.5-2B Q4_K_M, llama.cpp b11878, CPU only, 5 threads, 8192 context,
reasoning off, image token limit 512, temperature 0. Images are synthetic
bottle/price-strip fixtures with known geometry, visually inspected before
interpreting results. These are recognition/conversion tests, not a shelf
detector benchmark. Every run uses two real HTTP requests and a fresh application
cache; the server can reuse prompt KV state.

Baseline native-schema readings of `฿100` and `₽100` produce `B 100` and `P100`
respectively. Both become exact USD 100-cent prices (14.15 and 13.36 seconds).
The combined reader invents `$100`; its amount is discarded by separate-tag
mode, but the inaccurate separate transcript still becomes a false exact price.

An initial prompt listing currency examples improves THB but changes the RUB
sign into THB. That prompt is withheld. Its foreign-RUB result originally
passed only the estimate check; a saved `review.json` marks it failed under
the stronger transcription check. The probe now reports symbol fidelity and
price handling separately, and includes fidelity in overall success.

Final-code results:

| Printed tag / store / mode | Transcript | Price handling | Overall | Seconds |
| --- | --- | --- | --- | ---: |
| ₽100 / USD / native | P100 | estimated 229 cents; no false exact price | fails transcription | 4.50 |
| ฿100 / THB / native | ฿100 | exact 10000 minor units | passes | 14.32 |
| ₽100 / RUB / native | P100 | estimated 229 minor units; still needs review | fails transcription and exact-price recovery | 13.85 |
| ฿100 / USD / JSON | B100 | estimated 189 cents; no false exact price | fails transcription | 17.77 |
| FREE $0.00 / USD / JSON | FREE $0.00 | exact zero | passes | 13.71 |
| SAVE $1.00 / USD / native | SAVE $1.00 | estimated; savings not treated as selling price | passes | 14.25 |

The generic prompt also transcribes foreign THB correctly in native mode
(14.16 seconds); foreign RUB still reads `P100` (13.47 seconds). Those two
runs precede the ambiguous-letter guard. Across baseline, withheld example
prompt, generic prompt and final code: 15 completed runs, 30 HTTP calls,
zero application cache hits. Inaccurate RUB and JSON-mode THB transcription
remain open; this change prevents the observed false exact prices without
claiming those symbols are now reliably recognized. Combined-reading mode
is not established as fixed by these separate-tag probes.

Evidence directories under `/workspace/scratch/`:
`capture-extra-currencies-before`, `capture-extra-currencies-candidate`,
`capture-extra-currencies-final`, `capture-currency-symbols-generic`,
`capture-currency-symbols-verified`. The run index is
`capture-extra-currencies-run-index.json`; the withheld prompt is
`capture-price-symbols-example-prompt-candidate.py`.

## Deterministic verification

The initial currency matrix produces 165 failures and 36 passes on original
code. The later ambiguous-letter matrix produces 72 failures before its guard.
The final selection passes 2298 tests across 13 price/capture files in 6.00
seconds. It covers currency codes/signs, matching amounts, zero and fractional
prices, full-width normalization, unknown marks, conflicting numeric guesses,
non-selling labels, cached HTTP schema conversion in both output modes, and
preservation of existing prices. Forty-six existing LiteLLM async logging
warnings remain. Strict Pyright reports zero errors/warnings; server import,
probe compilation and diff checks pass. UI checks are inherited from integration
451. Published v0.8.2 notes and release assets are unchanged.
