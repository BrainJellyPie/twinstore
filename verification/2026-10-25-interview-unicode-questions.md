# Multilingual model questions survive deduplication

Question comparison removed every character except ASCII letters, digits and
spaces. Distinct Korean, Chinese, Japanese, Hindi and Arabic questions therefore
collapsed to an empty comparison key: follow-ups disappeared after a question
in that script had been asked, and group suggestions retained only one question.
The prompt asks for English, but a usable non-English model response should not
be silently discarded by the harness.

Twenty scripted HTTP cases reproduced the problem in 2.75 seconds across five
scripts, follow-up/group paths and JSON/JSON-schema modes. They include a truly
repeated question in a decomposed Unicode representation and an already-asked
question. Cached model replies go through the same postprocessing.

Comparison now applies Unicode compatibility normalization and case folding,
keeps letters, digits and combining marks, removes punctuation and normalizes
whitespace. Displayed wording is preserved. Native Chinese/Japanese and Arabic
ending punctuation no longer receives an extra ASCII question mark.

All 68 focused multilingual, personal-context, interview API and suggestion-race
checks passed in 8.59 seconds. Twenty existing LiteLLM async-logging cleanup
warnings were reported. No model inference or paid API calls were used.
Strict backend type checking passed with zero errors; `git diff --check` is clean.
