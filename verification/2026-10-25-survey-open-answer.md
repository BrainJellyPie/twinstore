# Require an answer in open-only surveys

The survey builder permits a questionnaire containing just the open question.
Its response schema nevertheless treated `why` as optional, so omitted, null,
empty and whitespace-only responses were cached and counted as successful
respondents despite yielding no measurements or verbatims. The prompt also
asked why the shopper had answered a prior question that did not exist.

Require a nonblank answer only when no other measured question is present.
Expose required/minLength constraints to native grammar, trim and validate the
answer before caching, and use a standalone opinion question in the prompt.
Keep the existing two-attempt correction budget and report repeated failures.
Explanations attached to ratings, prices or a usable preference question remain
optional, including the existing null-to-empty handling.

Before the fix, 30 new checks failed and one compatibility check passed in
3.18 seconds. Scripted HTTP covers both JSON modes, omission/null/empty/Unicode
whitespace, correction, repeated failures, invalid legacy caches, later recovery
and cached repeats. Assertions check respondent counts, empty-panel failure,
verbatims and the saved response. Controls preserve short negative and Korean
answers and optional explanations alongside ratings.

After the fix, 185 focused survey, price-bound/order, optional-explanation and
marketing checks passed in 9.98 seconds. Full source Pyright reported zero
errors and warnings. No native inference or paid model calls were used.
