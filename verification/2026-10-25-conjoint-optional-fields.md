# Optional notes in automatic conjoint drafts

Null context, rationale or comparable-product notes rejected otherwise valid
conjoint drafts. A direct probe reproduced each field, then scripted HTTP tests
reproduced eight response failures and two cache misses for legacy null entries
in 3.42 seconds. Fifteen required-field and malformed-type controls passed.

Only these optional notes use their existing empty-text/list defaults. The
prompt explicitly requests those forms. Prices, attribute axes, study name and
product remain strict, including null prices. Normalized studies still pass the
existing usability checks inside the correction loop before caching.

The regression retains exact attribute levels, 149/199 minor-unit price levels,
the supplied product/name and any remaining comparison notes. Cached null notes
and repeated results use the same boundary. All 112 focused optional-note,
semantic-recovery, price-boundary, attribute-level and API checks passed in 4.39
seconds. Ten existing LiteLLM async-logging cleanup warnings were reported.
No live model inference or paid calls were used.

`uv run pyright src/` reported zero errors and warnings. `git diff --check` passed.
