# Keep the intended questionnaire and customer quota in model drafts

A concept-test draft containing `APPEAL`, `20S`, or `female` previously failed
as a whole. The model-only draft now canonicalizes unique known strings in
questions, age groups and genders before literal validation. Other list-item
types and unknown labels still fail. Optional null quotas retain their existing
empty-list meaning, and required questions remain required. The prompt lists
the exact question-ID, age and gender spellings.

The real LiteLLM/Instructor HTTP matrix covers every allowed choice in both
JSON and JSON-schema modes, with swapped case and Unicode surrounding spaces.
It compares the full result to the canonical draft, checks both image IDs,
the 199-cent price and cache reuse, and passes the result into SurveyRequest
and the application's actual quota filter over all 12 age/gender combinations.
The selected persona IDs are identical to those of the intended canonical
quota; source personas are unchanged. Other tests retain existing question
ordering and deduplication, optional quotas, malformed-item rejection and API
builder output, alongside image ambiguity and monetary boundary checks.

Before the repair, 32 cases failed and 44 passed in 6.72 seconds. The focused
draft, optional-field, price/image-boundary and API suites then passed 160
checks in 3.86 seconds, with 43 known LiteLLM logging-cleanup warnings. Full
source Pyright reported zero errors and warnings. This used scripted provider
responses without native inference, model downloads or paid calls, and does
not measure model error frequency.
