# Keep receipt purchases when optional text is unreadable

Receipt transcription discarded an otherwise valid reading when an unreadable
store name, date, time or currency came back as null. The application caught the
validation error and displayed an unreadable-receipt placeholder, losing usable
product lines. These optional text fields already default to an empty string when
omitted; the model boundary now maps explicit null to that same default.

The prompt requests empty strings for unknown metadata and forbids inventing text.
The existing request-specific default currency still determines minor units. A
missing date remains unknown, and a known date without a time still requires review;
no midnight or date is inferred. Null product lists, product names and quantities,
other invalid metadata types, and invalid/nonfinite monetary amounts retain their
validation. Authored receipt-domain models are unchanged.

Before the patch, 30 HTTP regressions failed and 15 invalid-structure/type controls
passed. Coverage includes both structured modes, USD/KRW/JPY, each optional field
and all four together, product/quantity/amount preservation, currency conversion,
separate receipt IDs sharing a cached reading, product matching and review status.
Focused OCR numeric/currency/amount, timestamp, review and vision-input checks:
157 passed in 3.94 seconds, with 30 existing LiteLLM logging-cleanup warnings.
Strict Pyright: zero errors. Responses were scripted; no live inference was used.
