# Preserve preferences when customer generation has no category list

The application generates project-wide customers without passing a category
list. The optional-field guidance added an instruction to use an empty preference
list whenever no category list was supplied. A model following it would erase
all category preferences, although the rule planner uses those preferences to
make planned purchases. Valid empty output cannot be distinguished from this
prompt-induced loss by schema validation.

Choose the category instruction according to the actual request. With a supplied
list, keep the existing exact-label rule. Without one, infer short English
category labels from the customer's needs and purchase intent, excluding brands
and specific products. Remove the conflicting blanket supplied-label instruction
for this field. Truly absent preferences still accept an empty list or null;
the existing optional-field normalizer is unchanged. The changed system prompt
also changes the response-cache identity.

Before the change, 16 default/empty-list prompt-contract checks failed and eight
supplied-list controls passed in 3.32 seconds. Scripted HTTP responses exercise
the real application generation wrapper, LiteLLM, Instructor and cache in both
JSON modes, USD and KRW. Tests inspect the actual transmitted prompts and carry
both inferred preferences and deliberate empty preferences into the rule planner:
the former can produce a planned tea purchase, while the latter remain empty.
They do not measure native model compliance or claim an observed production
conversion-rate change.

Focused generation, batching, context recovery, optional-field and estimate
tests passed 222 checks in 9.34 seconds. Full source Pyright reported zero errors
and warnings. One existing LiteLLM async logging cleanup warning was emitted.
No native inference, downloads or paid requests were used.
