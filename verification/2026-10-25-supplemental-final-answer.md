# Final answers in uploaded customer-data summaries

The supplemental CSV/XLSX pipeline accepted explicit model thoughts as its
final data summary. In the real LiteLLM HTTP path, leading whitespace with
multiple thought blocks and an unfinished thought survived provider parsing.
Eight cases reproduced contaminated summaries; twenty plain-text, literal-tag,
provider-cleaned and length-limit controls passed in 3.11 seconds.

The summary boundary now removes explicit leading `<think>` blocks before
trimming the final answer to the existing 2,000-character storage limit. The
same parsing rule already used for structured answers is shared without
changing the general raw-text client contract. A reasoning-only or unfinished
response returns the existing empty-summary result. It does not fabricate an
alternative summary or stop the existing customer-generation fallback.

The HTTP tests run actual CSV/XLSX parsing, structured column selection,
statistics aggregation and raw summary completion, then pass the result into
the real customer-location request. They verify exact final evidence, absence
of the hypothetical spending claim, bounded stored text and unchanged request
and token accounting. Already saved metadata is not rewritten automatically.
No native inference or paid API was used.

All 120 focused summary, structured-thinking, CSV-format and upload-retry
checks passed in 4.43 seconds. Sixteen existing LiteLLM logging-cleanup
warnings occurred. Pyright reported zero errors/warnings; diff checks passed.
