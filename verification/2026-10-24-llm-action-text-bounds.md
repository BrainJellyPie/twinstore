# Keep repeated action narration out of subsequent model context

Intent and impulse responses allowed unlimited reasoning and action descriptions.
The next impulse prompt copies every intent action's description. One repeated
description could therefore make an otherwise small store/customer request exceed
a local server's context, losing the shopper after earlier stages had succeeded.
Grammar-capable servers also had no string-length bound to stop that repetition.

Model responses now use a generated-action schema with descriptions bounded to
400 Unicode characters, and reasoning is bounded to 600. Before validators clip
only these narrative fields for providers that ignore JSON grammar bounds.
Prompts ask for concise, non-repetitive text. Exact SKUs, quantities, coordinates,
action count and other structural fields remain intact. Authored and rule/VLM
domain actions keep their original descriptions. The existing model boundary
still copies input actions, strips internal offer hints and preserves strict JSON
coordinate parsing. The new schema also gives new requests their own cache key.

An offline Qwen tokenizer probe used one synthetic repeated description among
five ordinary visit actions. Its resulting stage-three text had 14,665 tokens for
either 62,000 English characters or 32,000 Korean characters. After normalization
and the prompt update, the corresponding texts had 790 and 875 tokens. Counts
exclude chat-template and schema overhead; they demonstrate prompt expansion,
not the frequency of repetition in live inference. The remaining catalog and
action count are not capped by this patch, so it does not guarantee that every
possible store fits a particular context window.

Before repair, 23 regression cases failed and 18 controls passed. After repair,
283 focused checks passed in 3.18 seconds, covering both route orderings,
English/Korean/emoji repetition, exact Unicode boundaries, actual three-stage
HTTP through OpenAI/LiteLLM/Instructor, JSON/JSON_SCHEMA modes and cache reuse.
Related purchase amounts, exposure, product limits, engine-field normalization,
strict coordinates and pattern text checks passed. Strict Pyright reported zero
errors. Eight existing LiteLLM logging-cleanup warnings occurred. All model/HTTP
responses were scripted; no model weights or paid inference were used.
