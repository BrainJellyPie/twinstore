# Preferred categories reach vision-model shelf glances

The entrance plan used preferred categories, but the later shelf-glance prompt
omitted them. When all other facts stayed the same, changing a shopper from
snacks to caffeine-free tea and fresh fruit produced an identical request and
reused the previous cached shelf answer. A direct prompt comparison and eight
scripted HTTP cases reproduced the omission; the HTTP baseline failed all eight
cases in 2.54 seconds.

Nonempty preferred categories are now included as shopper evidence beside the
existing intent and habits. This does not restrict the model to those categories.
The tests exercise changed, cleared, multilingual and repeated category values
in both JSON and JSON-schema modes. They retain real route exposure, rendered
shelf images, response parsing and disk caching while fixing the plan and using
an offline HTTP transport. Identical evidence reuses the cache; changed evidence
causes a fresh request and preserves the existing intent and basket context.

All 41 focused preference, exact-basket and vision-glance tests passed in 30.89
seconds. No live model inference or paid API calls were used.
Strict backend type checking passed with zero errors; `git diff --check` is clean.
