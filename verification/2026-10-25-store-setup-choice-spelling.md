# Preserve a valid store form despite known code spelling variations

Replies containing `Weekday` or `krw`, including surrounding whitespace,
rejected the entire store-creation draft even when the name, description,
address, format and hours were valid. Only the model-facing opening-day and
currency fields now trim and normalize case before their existing literals
validate them. Unknown codes, synonyms and wrong types still fail; null means
unspecified. The public result model remains strict. The prompt now explicitly
maps every day to `7`, weekdays to `weekday`, weekends to `weekend`, and asks
for uppercase ISO currency codes.

Real LiteLLM/Instructor HTTP tests cover both structured-output modes and all
nine combinations of the three day choices and three currencies. They verify
canonical codes, the 0–24 boundary, localized name/description, unchanged
address/rationale, selected format/type and cache reuse. API coverage adds a
mixed-case/space reply to the existing complete form test. Controls retain
unknown-code rejection, nulls and strict public values. Existing exhaustive
opening/closing-hour pairs and format-name ambiguity checks also pass.

Before the repair, 19 cases failed and 39 passed in 5.27 seconds. The focused
setup/form/boundary suites passed 922 checks in 4.23 seconds, with 37 known
LiteLLM logging-cleanup warnings. Most cases in that count are the existing
fast hour-window matrix. Full source Pyright reported zero errors and warnings.
Responses were scripted; no native inference, model downloads or paid calls
were used, and no model error frequency is claimed.
