# Keep malformed weekday restrictions from broadening a scenario

The generated scenario schema accepted unrestricted integers for weekdays,
then conversion silently removed values outside 1–7. Responses such as `[0]`
or `[8]` became `[]`, which means every day. Mixed valid and invalid restrictions
also lost part of the model's answer without correction or a warning.

Apply the domain's existing 1–7 item bounds to the model-response schema and
state the mapping explicitly in the prompt. The grammar exposes the same
bounds, and runtime validation runs before caching. Conversion retains sorting
and deduplication without silently deleting invalid days. The API now rejects
an uncorrected invalid draft instead of returning an unrestricted scenario.

Thirty-six scripted HTTP failures were reproduced in 3.34 seconds, with five
valid controls. Both JSON modes cover all-invalid and mixed weekday lists,
correction, repeated failures and invalid legacy cache entries. Tests apply
the resulting scenario to all seven weekdays: a corrected Friday restriction
keeps exactly Friday's persona. Explicit `[]`, Monday, Sunday, multiple days
and duplicate valid days retain their behavior.

Afterward, 97 focused generation, API, weekday, clone and event checks passed
in 4.44 seconds. Pyright reported zero errors and warnings. The API fixture now
uses a valid weekday; a separate API regression checks malformed model days.
No live model inference or downloaded model was used.
