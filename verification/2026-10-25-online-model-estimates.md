# Account for reminder visits in model-work estimates

A shopper with a three-click limit can make six model decisions across the first
and reminder visits. The launcher previously counted one visit and could also
show an estimate of 330 calls above its own maximum of 90 for a 30-shopper,
three-click run without surveys.

Site summaries now expose the saved reminder setting. The launcher totals one
possible visit for each known ordinary store and two for reminder stores and
reminder experiments. An older or unavailable summary reserves two visits;
confirmed quick-experiment copies retain their own setting on retry. One exit
survey per shopper/store is counted separately, matching the runner. The
heuristic estimate is bounded by the click limit. All six languages now label
clicks per visit and distinguish model decisions/surveys from extra retry calls.
No simulated visit or provider retry behavior changed.

A direct offline session reproduced six model requests with max_steps=3.
Before repair, the summary API regression and seven frontend estimate cases
failed; seven frontend controls passed. Cases cover reminders on/off, 3/24
clicks, surveys on/off, reminder experiments and unknown selected summaries.
The API test covers creating, editing and copying the stored reminder setting.

After repair, 10 backend API/reminder tests passed in 11.16 seconds; 71 frontend
launcher, experiment and localization tests passed in 6.60 seconds. Full-source
Pyright reported zero errors and warnings; backend boot passed. TypeScript,
changed-file ESLint with zero warnings, and production build (18.34 seconds)
passed. No paid inference or model downloads were used.
