# Cover every answer in the theme-coding grammar

ThemeCoding previously allowed an assignment list of any length. A local grammar
decoder could legally finish with zero assignments, after which all substantive
customer answers were counted as Other. The prompt requested coverage, but the
output grammar did not represent it.

Each request now supplies matching minItems/maxItems equal to its actual answer
count. The field description and prompt specify one assignment per answer in its
original order, including repeated answers. These are grammar constraints only:
non-enforcing providers still use the existing explicit Other fallback for missing
or invalid indices. Label cleaning, theme merging and the six-theme display cap
are unchanged.

The pre-fix HTTP cases reproduced all-Other reporting in both structured modes
for 4, 5, 17, 159, 160 and 170 source answers (the existing report cap keeps 160).
After the fix, all 44 focused tests pass in 16.46 seconds. Checks cover whitespace
filtering, kept-answer counts, arm-specific theme counts and shares, cached reuse,
short/surplus/invalid responses, label remapping, group-interview APIs and persisted
study readings. Strict Pyright reports zero errors. Eleven known LiteLLM logging
cleanup warnings were emitted. Model responses were scripted to exercise legal
grammar termination; no live model inference was performed.
