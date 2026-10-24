# Keep valid edits when irrelevant text fields are null

Local responses often populate every field in the shared edit shape, using
null for fields irrelevant to the selected operation. A complete price edit,
for example, failed because its unused shelf or sign text was null. Both
automatic layout editing and A/B drafting exhausted their correction budget.

Share a field validator between the two draft shapes. After validating the
operation kind, convert only irrelevant null text fields to their existing
empty defaults. Required targets and sign text remain strict, as do malformed
nonnull values and numeric operation validation. Prompts ask for empty strings
in unused text fields. No domain or manually submitted change schema changes.

Before the fix, all 22 HTTP cases failed and 11 strict-input controls passed
in 4.63 seconds. Tests exercise both JSON modes and all supported operations:
price, discount, sign, move, category price, and A/B package replacement. They
verify actual resulting prices, placements, image selection, engine choice,
unchanged source layouts and cached repeat calls without additional requests.

After the fix, 207 focused drafting, correction, boundary and API checks
passed in 8.16 seconds. Pyright reported zero errors and warnings. The 22
pytest warnings are existing LiteLLM asynchronous logging cleanup warnings.
No native model inference or model download was used.
