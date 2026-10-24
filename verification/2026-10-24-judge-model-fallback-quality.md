# VLM layout judge model-call failures

The judge checked completed shoppers and paired their outcomes, but a completed
journey can use fallback entrance plans or skip failed shelf glances. Scripted
arms with 100% model-call failures still returned valid-looking VLM winners.
Entrance failures were retained as a counter; glance failures were not used to
qualify the result. A bad calibration pilot could also trigger further work.

Read the engine's existing plan/glance outcome counters immediately after each
arm. Match the marketing and venue-study policy: more than half failed stops
judging with the affected arm, counts and provider recovery guidance. A failing
calibration baseline stops before calibration/search; a failing candidate stops
before subsequent panels. The existing application failure handler prevents a
completed result from being written. Smaller failures, including exactly half,
are disclosed per arm in both judge and overall optimization notes.

The initial 24-case matrix had 21 failures, including missing warnings as well
as missing rejection. Cases cover baseline/candidate, calibration on/off,
entrance-only/glance-only/combined failures, 50%/51%, all failures and zero calls.
82 focused judge and incomplete-panel checks passed in 3.43 seconds; Pyright
reports zero errors. Tests verify that later arms and calibration do not run
after rejection and clean arms retain their winner. No live/paid model calls,
full suite or frontend rebuild. Ordinary simulation fallback behavior is unchanged.
