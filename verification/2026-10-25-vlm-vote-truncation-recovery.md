# Apply bounded truncation recovery to voting-model members

A scripted model that truncated its first entrance response received budgets
410 then 820 when used alone and answered successfully. The same model in a
voting ensemble received only 410 and failed. Both voting entry plans and
shelf glances bypassed the engine's existing single-model recovery, which
could exclude recoverable votes and change the combined decision.

The ensemble call now accepts an optional second output budget. Each member
uses it at most once, only after a typed `IncompleteOutputException` from the
terminal attempt (including Instructor wrappers). VLM entry and glance votes
opt into the same doubled budgets as their single-model counterparts. Successful
members return immediately; validation, authentication, configuration and
other failures do not trigger this retry. Seeds, routes, prompts, response
schemas and member order are retained. Generic ensemble callers keep their
existing no-recovery default. Application-built members share base sampling
settings, including the glance budget.

Thirty actual LiteLLM/Instructor HTTP cases cover both structured modes and
text entry, image entry and shelf-glance paths. A successful member is never
re-asked while two other members recover, remain truncated, return invalid
generated text, or receive HTTP 400/403. Recovering two walkout votes changes
the previously lone entering vote to the correct combined walkout. Checks
verify exact budgets, unchanged messages, votes, cache reuse and bounded
persistent failure. Four typed-wrapper controls inspect the terminal failure;
one control preserves default generic-ensemble behavior. The pre-fix run had
16 failures and 19 passes in 3.71 seconds: twelve failures were missing HTTP
recovery, and four exercised the not-yet-added opt-in argument.

The focused run passed 237 checks in 49.01 seconds with three existing LiteLLM
logging cleanup warnings. One older glance test expected a hallucinated
product to reach resolution as `invalid`, whereas the visible-product schema
already rejects it as an `error`. That same test failed independently on the
unchanged pre-fix main commit 6afc41bfce4d6115c39b8d3d647024d8930ed785.
Its expectation now checks the existing validation-error count and continued
absence of impulse purchases; the rerun passed in 4.09 seconds. In total,
238 distinct checks passed. Full source Pyright reported zero errors and
warnings. No native inference, model weights or paid calls were used.
