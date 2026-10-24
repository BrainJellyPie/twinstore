# Correct contradictory generated customer budgets

Generated customers accepted and cached a minimum budget greater than a positive
maximum, such as 500–100 minor units. Shopping prompts then displayed that
contradictory range while execution enforced the lower maximum.

Validate the relationship in GeneratedPersona before the batch can be accepted
or cached. Ask for correction through the existing three-attempt budget and
clarify the rule in the generation prompt. Do not swap or invent either amount.
Keep equal bounds and budget_max=0 as an unspecified upper limit, including a
positive minimum. Internal/authored Persona compatibility is unchanged.

Before the fix, 19 cases failed and six controls passed in 2.74 seconds.
Scripted HTTP covers both JSON modes, small/ordinary/safe-integer boundary
inversions, successful correction, repeated failures, legacy cache revalidation,
later recovery and cached repeats. The numeric-field boundary test now holds
the other bound consistent so it continues testing representability separately.

After the fix, 156 focused budget, customer-generation and failure-preservation
checks passed in 5.04 seconds. Full source Pyright reported zero errors and
warnings. No native model inference was used.
