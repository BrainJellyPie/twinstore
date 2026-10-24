# Optional impulse actions preserve the planned visit

A local model can return `actions: null` when it has no additional reaction.
The impulse stage already accepts an omitted list or `actions: []`, but the null
form failed validation and discarded the otherwise valid planned purchase.
The initial direct-model probe reproduced the difference for both route
orderings. The scripted HTTP regression then failed all eight null combinations:
JSON and JSON-schema modes, planned and nearest ordering, with and without
input-context recovery. Thirty normal/invalid-format controls passed. The
baseline took 4.44 seconds; no model inference or paid API was used.

Only `ImpulseResponse` normalizes a null action list to the existing empty-list
default. Its prompt explicitly asks for an empty array when there is no extra
reaction. `IntentResponse` remains strict for null actions. Objects, strings,
booleans, numbers and lists with invalid members remain invalid in both base and
catalog-constrained impulse schemas.

The new tests also exercise a cached null reply. Each successful visit retains
the original planned SKU, quantity, amount and origin; pays exactly once; exits
normally; and leaves the store unchanged. Focused recovery keeps its candidate
trace and reuses its successful responses from cache. The 116 focused optional
actions, context recovery, narration and engine checks passed in 8.34 seconds.
Strict backend type checking passed with zero errors, and `git diff --check`
is clean.

This change was prepared in a separate worktree while v0.4.13's release checks
ran. It is a follow-up change and is not part of the v0.4.13 release candidate.
