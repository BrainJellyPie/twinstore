# Do not describe an unspecified budget as zero spending money

The domain and executors treat budget_max=0 as no fixed budget cap, including the
default for generated/imported customers with no budget information. Pattern and
intent prompts instead formatted it as `0~0` (or a positive minimum followed by
zero), giving the model conflicting information before it decided whether to buy.

The shared budget fragment now states that no fixed upper budget is specified.
When a positive minimum exists, it remains visible with its currency units.
Positive upper bounds keep their exact previous range formatting. Execution
limits and the impulse prompt's existing omission of unspecified budgets are
unchanged. The changed prompt naturally separates previously cached zero-range
pattern/intent answers from the corrected requests.

Before the change, 12 HTTP prompt-contract cases failed and 25 positive-budget
controls passed. Tests cover both structured modes, USD/KRW/JPY, zero or positive
minimums, both affected request stages, three-unit checkout and cache reuse.
Positive-budget controls also cover EUR, lowercase VND and the JavaScript-safe
integer boundary. Focused budget, pattern, intent recovery, compact impulse and
generated-budget verification passed 162 tests in 6.86 seconds. Strict Pyright
reported zero errors. Responses were scripted; no live inference or purchase-rate
improvement measurement was performed.
