# Keep usable layout briefs with unknown optional fields

Null optional lists or rationale rejected an otherwise valid generated layout
brief. This discarded usable size, style and color edits. The existing omitted
field behavior was an empty list or string, leaving current settings intact.

Normalize only null `excluded_categories`, `not_expressible` and `rationale`
to their existing defaults. State the distinction between empty lists/text and
nullable scalar options in the prompt. Conversion still preserves current
exclusions and untouched colors, and reports out-of-range requested options
without applying them. Wrong non-null types remain invalid.

Sixteen scripted HTTP failures were reproduced; thirteen omitted-field and
malformed-type controls passed in 3.73 seconds. Tests cover both JSON modes,
each optional field and all together, valid and out-of-range width changes,
merging the reviewed patch into actual LayoutOptions, preservation of the
input options and reuse of valid cached responses.

Afterward, 880 focused brief, API and setup/goal boundary checks passed in 4.28
seconds. Pyright reported zero errors and warnings. The 19 pytest warnings are
existing async logging cleanup warnings. No real model inference or model
download was used.
