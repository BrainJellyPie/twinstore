# Keep valid questionnaires when the preference letter changes case

Survey preference choices use the offered letters A–D. A lowercase letter or
surrounding whitespace exhausted model correction attempts, marked the respondent
as failed and discarded otherwise valid ratings from the same questionnaire.

The generated survey schema now canonicalizes a preference against only its
offered letters before literal validation. Required choices and transmitted
schema enums remain unchanged. Missing, blank, null, multiple, descriptive or
unoffered choices are not guessed. A one-image survey still has no preference
field, and an open-only survey still requires a substantive answer.

Thirty-six actual LiteLLM/Instructor HTTP cases cover every offered letter for
two, three and four stimuli, lowercase and Unicode-whitespace variants, and
both JSON modes. They retain all supplied ratings, produce the correct report
preference share and respondent count, need only one model call, save canonical
cache values and revalidate altered cached spellings. Ten invalid-choice cases
and one schema/single-image control retain the boundaries.

Before the fix, all 36 HTTP cases failed and 11 controls passed in 3.86 seconds.
The focused choice, open-answer, price-order, price-bound and optional-reason
suite passed 209 tests in 5.88 seconds without warnings. Full source Pyright
reported zero errors and warnings. Model responses are scripted; no native
inference, downloads or paid calls ran.
