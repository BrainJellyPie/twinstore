# Keep padded catalog names in their intended purchase category

An entry plan naming `Original` in `Milk` bought the 100-priced `Original` from
`Snacks` when the milk shelf's 700-priced product was stored as ` Original `.
The resolver stripped the model's product name but not the catalog name. It
therefore missed the literal match in the named category and returned a
different category's unpadded global match before considering category-local
word matches. The same failure affected two placements of one SKU.

Exact and grammar-bounded prefix comparisons now trim both sides, including
the exact/prefix diagnostic. Original catalog names, SKU identities, prices,
interior whitespace and stored layouts remain intact. When no category is
specified, all equal normalized names remain candidates; the resolver does
not invent a unique identity. Existing category fallback and seeded offer
selection behavior are unchanged.

Sixty-four HTTP cases run actual LiteLLM/Instructor responses through entry
planning and purchase execution in both structured modes, with reversed
catalog order, shared or distinct SKUs, ASCII and Unicode whitespace, and
`Original`, `X`, `茶` and `Straße` names. They verify the intended rack, SKU,
700 price, shelf level, quantity, spending, exact-match diagnostic, repeated
cache reuse and source immutability. Eight cases cover clipped long names,
two preserve unqualified ambiguity, and one preserves distinct interior
spacing. Before the fix, 74 cases failed and the interior-spacing control
passed in 4.23 seconds.

The focused VLM planning, category, clipped-name, offer and basket suite passed
315 tests in 19.08 seconds with 64 existing LiteLLM logging cleanup warnings.
Full source Pyright reported zero errors and warnings. Responses were scripted
through the real HTTP stack; no native model inference, weight downloads or
paid calls were made. The defect occurs after a correct model choice, so the
test establishes the resulting offer and purchase without claiming model
recognition accuracy.
