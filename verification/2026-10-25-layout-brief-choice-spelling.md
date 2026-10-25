# Recover known design choices in model-written layout briefs

A local-model reply such as `Loop`, ` NEAR_ENTRANCE ` or `BOTANICAL` previously
rejected the entire layout brief, including independent valid size, color and
assortment edits. The model-only draft now trims surrounding whitespace and
case-folds its nine lowercase choice fields before their existing literal
validation. The prompt requests the exact lowercase values and underscores.
No domain or direct layout-options API validation changed. Unknown designs,
synonyms, changed internal separators and wrong types remain invalid; optional
null choices still preserve current settings.

The HTTP matrix covers all 45 allowed choices in both JSON and JSON-schema
modes with uppercase spelling, an ideographic leading space and a trailing
tab. It uses real LiteLLM/Instructor parsing and checks the complete result
against the canonical reply, merged current options, unchanged unrelated
dimensions/till counts, color and category preservation, source immutability,
annotation case, and cache reuse. Null and malformed-choice controls cover
all nine fields. The API test also exercises exact, title-case and padded
uppercase multi-field replies while retaining its invalid-size/color/category
warnings and applicable edits.

Before the repair, the new HTTP/API cases reproduced 92 failures; 107 controls
passed in 15.23 seconds. After the repair, the focused layout-brief suites
passed 242 checks in 6.76 seconds, with 109 known LiteLLM logging-cleanup
warnings. Full source Pyright reported zero errors and warnings. Tests use
scripted provider responses; no native inference, model weights or paid calls
were used, and this does not measure model error frequency.
