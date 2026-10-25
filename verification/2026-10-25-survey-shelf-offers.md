# Preserve shelf-price evidence in concept survey drafts

Concept design built a single `SKU -> description` dictionary. When a product
appeared on both an ordinary shelf and a differently priced promotional shelf,
the last placement silently overwrote the first. A question about the ordinary
shelf could therefore receive only the promotional price. Changing an earlier
placement did not change the model prompt or its cached draft.

The application now gathers distinct shelf descriptions per SKU, removes exact
copies and ranks them using the existing question-relevance logic. An image
lists at most four offers with an explicit omitted-offer count. This keeps
input growth bounded while retaining a named shelf beyond the initial entries.
Prices remain in the store's units and are excluded when the requested survey
currency differs. The draft prompt asks the model not to choose between offers
by listing order; with several offers it should use a reference price only
when the question identifies the offer or states a price.

Sixteen new regression cases failed before repair in 2.90 seconds. Twelve use
the real application-to-LiteLLM/Instructor-to-HTTP path in both JSON modes,
USD/KRW/JPY and reversed rack orders. Distinct prices both reach the prompt;
identical copies appear once; changing the earlier offer invalidates the draft
cache and unchanged repeats reuse it. Four 40-offer cases retain the named
Backcorner shelf, cap the listing at four and report 36 omitted offers,
including reverse-order and foreign-currency controls. Store data is unchanged.

All 168 focused draft API, price, boundary and spelling tests pass in 5.08
seconds. Full-source Pyright reports zero errors and warnings; the final
prompt-only clarification narrows the reference-price rule to multiple offers.
Tests emit 43 existing LiteLLM logging coroutine warnings. No full suite,
weights, native inference or paid calls were used. Actual model compliance
with the multiple-offer instruction is not measured by scripted responses;
the study remains a user-reviewed builder draft.
