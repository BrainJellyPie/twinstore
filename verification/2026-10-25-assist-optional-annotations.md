# Keep valid assistive outputs when optional explanations are null

Four assistive paths rejected otherwise usable outputs when a local model gave
null for the optional explanation: route.reason, optimizer.rationale,
script.differs_by and hypothesis.why. Existing omission defaults already allowed
these explanations to be absent.

Normalize only those fields to empty strings and state the convention in each
prompt. Preserve the chosen tool, optimizer objective/scope/limits and locked
shelves, exact script and proposed test. Required content, malformed non-null
explanations and operational choices remain strict. A null lock list is still
invalid, and tools requiring a completed run remain unavailable without one.

Before the fix, eight cases failed and 40 controls passed in 3.28 seconds.
Scripted HTTP covers all four workflows in JSON and JSON-schema modes, null,
omission and explicit Korean explanations, source immutability and cached
repeats. Assertions check exact routing, unavailable-tool filtering, shelf IDs,
minimum improvement, script wording and test type/question. Negative controls
cover malformed explanations, invalid choices, null locks and missing content.

After the fix, 880 focused assistive, setting-boundary, optimizer API and script
API checks passed in 3.63 seconds. Full source Pyright reported zero errors and
warnings. No native model inference or paid model calls were used.
