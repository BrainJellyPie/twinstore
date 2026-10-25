# Retain purchased receipt lines whose names are unreadable

Receipt conversion discarded every model-written line with a blank name, even
when its quantity and paid amount were readable. A two-line scripted receipt
therefore became one line and passed review as ready when no printed total was
available. This silently lost sales evidence before the user could correct it.

Blank-name purchased lines now keep their position, quantity and amounts.
The prompt explicitly asks the model to retain them with an empty name.
Catalog matching leaves them unmatched, and existing review validation blocks
export until the user chooses a product or explicitly excludes the line.
The current review UI already displays a localized line-number fallback and
product selector for blank names. No product or missing amount is invented.

Thirty-two HTTP cases use real LiteLLM and Instructor with scripted responses:
both output modes, USD/KRW, empty/Unicode-whitespace names, discounted totals,
fractional quantities, free items and unreadable amounts. They check preserved
line order, blocked review, manual correction and CSV/POS amounts, explicit
exclusion, cache reuse and unchanged input. API tests also verify retained
blank rows and unmatched counts. Existing null-name/type validation remains.

Before the repair, 36 checks failed and 18 passed in 5.16 seconds. Focused
receipt, numeric, bound, metadata, review and API suites then passed 174 checks
in 6.85 seconds, with 62 known LiteLLM logging-cleanup warnings. Full source
Pyright reported zero errors and warnings. No native model inference, model
download or paid call was used; unreadable-name frequency was not measured.
