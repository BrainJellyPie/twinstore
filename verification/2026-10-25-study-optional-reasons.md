# Retain measured study answers without an explanation

Null explanation text rejected otherwise valid concept-survey ratings, conjoint
choices and shelf-test answers. The panel marked the respondent as failed, and
aggregations excluded it; a failed shelf-test arm also removed its paired
comparison. An omitted explanation already used an empty string.

The three study-response schemas share normalization of null `why` to that
existing empty default. Prompts explicitly request empty strings. Required
choices, ratings, prices and noticed-product lists are unchanged. Other wrong
explanation types and overlong text remain invalid, and no measured answer is
invented or changed.

Twelve failures were reproduced through real LiteLLM/Instructor HTTP parsing;
forty omitted/text explanations and invalid-type controls passed in 2.96
seconds. Both JSON modes cover affirmative choices and explicit refusals,
minor-unit price conversion, Likert counts, no-purchase shares, paired shelf
comparison and exact response-cache reuse.

The fix passed 192 focused panel, personal-context, choice-instruction, price
and visible-badge checks in 7.53 seconds. Pyright: zero errors and warnings.
Two pytest warnings came from existing LiteLLM async logging cleanup. No live
model inference or downloaded model was used.
