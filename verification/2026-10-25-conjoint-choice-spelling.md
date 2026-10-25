# Preserve unambiguous conjoint choices

Conjoint responses used exact string literals for every task. An otherwise
valid response containing a lowercase product letter or padded uppercase NONE
failed the entire respondent, discarding all task answers. Small models and
providers that ignore the transmitted grammar can emit these clear variants.

Task fields now use the existing unique-identifier canonicalizer before literal
validation, against only the options actually offered in this questionnaire.
The wire schema still lists canonical letters and includes none only when
no-purchase is allowed. Explanations retain their existing handling. Missing,
null, multiple and unoffered selections are not guessed, and a forced-choice
study cannot gain a no-purchase option through normalization.

Seventy-two actual LiteLLM/Instructor HTTP cases cover both JSON modes, two to
four alternatives, three/eight/fifteen tasks, optional no-purchase choices and
case variants with/without Unicode whitespace. They verify every recorded
choice, the estimation matrix, no-purchase share, canonical cache writes and
revalidation of spelling variants in cache. Twenty-three controls reject
invalid, missing and unoffered choices. Before the change, 72 cases failed and
23 passed in 4.36 seconds.

The focused suite had 421 passing cases; eight new assertions incorrectly
compared the existing four-decimal no-purchase share with an unrounded fraction.
After correcting those assertions and a typing-only choice-list adjustment,
the eight remaining cases passed in 2.48 seconds, for 429 distinct passing
checks. Full source Pyright reported zero errors and warnings. The initial
focused run had two existing LiteLLM logging cleanup warnings. No native model
inference, model downloads or paid calls ran; responses are scripted.
