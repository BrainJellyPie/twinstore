# Null shopping lists on explicit walk-outs

An `enter=false, items=null` answer failed validation even though no shopping
list would be executed. On the first response this failed the shopper; after
a successful earlier plan it activated the rule-plan fallback instead of
respecting the model's walk-out. Eight HTTP cases reproduced these two failures
across text/image entrance requests and both JSON modes. Twenty-eight empty,
omitted and invalid-type controls passed in 2.62 seconds.

The item boundary now uses an empty list only when the already validated entry
decision is explicitly false. Null lists on entering/default-entry responses,
malformed entry flags and non-null malformed item lists still fail validation.
The prompt already requests an empty list when the shopper turns away.

The regression executes real model-client responses through the VLM planner and
shopper executor. It checks the original walk-out narration, no purchases,
browses or payment, zero spend, exit, no rule fallback, repeat-cache reuse and
legacy cached null lists. Source inventory remains unchanged. No native model
inference or paid calls were used.

All 160 focused walk-out, vote, narration and VLM-plan checks passed in
18.46 seconds. Thirty-one existing LiteLLM logging-cleanup warnings occurred.
Pyright reported zero errors and warnings; `git diff --check` passed.
