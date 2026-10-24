# Distinguish missing vision measurements from explicit zero interest

The model-facing shelf schema inherited the internal ShelfGlance default of
zero interest. An empty response or a named product without a score therefore
looked successful, lowered ensemble interest and entered photo-comparison
statistics as a measured answer. It was also cached as valid.

Make interest required only in the dynamically constructed model response.
Keep internal ShelfGlance defaults and explicit zero scores. Missing scores
now follow the existing failed-response handling and are excluded from valid
votes and photo-panel answers, without adding retries. Revalidate old cache
entries using the required field. The prompt explicitly requests this score.

All 19 new cases failed before the fix in 2.64 seconds. Scripted HTTP covers
both JSON modes, empty/partial responses, single-model and voting clients,
invalid legacy cache entries, later explicit refusals and cached reuse. Photo
panels verify error counts and exclusion from agreement statistics; explicit
zeros remain valid measured refusals.

The wider focused run passed 166 cases in 38.94 seconds, with three truncation
test fakes still returning an empty object as their successful answer. Update
those fakes to provide an explicit zero score or entry decision. The final
46-case measurement/truncation run passed in 2.73 seconds, completing the 169
distinct focused cases without repeating the slower rendering checks. Pyright
reported zero errors and warnings. The final three pytest warnings are existing
LiteLLM async logging cleanup warnings. No native model inference was used.
