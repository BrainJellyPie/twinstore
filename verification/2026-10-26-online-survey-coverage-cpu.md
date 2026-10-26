# Unanswered online exit surveys remain visible

2026-10-26, based on main `a21c08af`, also integrating upstream
`3e2c3b82` (wider online reading-time variation). Actual CPU inference uses
Qwen3.5-0.8B Q4_K_M with the F16 vision projector, llama.cpp b11878,
five CPU threads and an 8K context. Local artifacts are under
`/workspace/scratch/cpu-vlm-probe`.

## Reproduced report failure

The actual JSON-mode visit
`online-session-unavailable-mobile-json-1792981428355411362` makes three
valid browser decisions but copies the survey schema on both survey attempts.
It has no usable survey. Replaying that saved session through production
report assembly completes the run, omits its survey summary and reports only
the generic virtual-shopper note. The absence of survey answers is invisible.
This report replay makes zero new model calls; it does not retest inference.

Reports now state the number of missing requested survey answers separately
for each variant. Missing answers remain excluded from ratings rather than
being assigned zero. Rules, disabled surveys and rival visits do not request
surveys and are not counted as missing. The browsing fallback note now uses
the number of browsing decisions, excluding survey calls from its denominator.
The total model-request counter still includes requested surveys.

After the change, the same saved session produces a completed report with
`Exit surveys for Threadline: 1 of 1 requested surveys had no usable model
answer. Survey summaries exclude missing answers.` Its survey remains null.
Before/after metadata and reports are in `survey-report-before` and
`survey-report-after`. The scratch replay explicitly raises if model inference
is attempted.

## New actual purchase visit

`online-session-purchase-desktop-json_schema-1792983806597706220` is a fresh
CPU VLM visit with three actual HTTP calls, no application-cache hits, 24.18 s.
It searches for `Cotton T-Shirt`, then leaves. The screenshot and prompt were
inspected: the requested product is the first result, costs $19.99 against a
$50 budget, and the page loaded in 0.6 s. The model nevertheless describes a
slow page and confusing sorting, then gives a survey of 1/1/0/false and says it
could not find what it wanted. There is no search-result omission to repair.

This run is structurally successful, with no rule fallback or invalid survey,
but does not complete the buying goal. The probe records those separately.
No purchase is forced and no action is reconstructed from the thought text.
The report fix does not solve these model reasoning problems or JSON-mode
schema copying. This inference preceded the reading-time branch integration.

## Focused verification

The new 11-case survey-coverage suite has six failures and five passes before
the fix. It covers text/vision, all/partial/no missing answers, a valid zero
recommendation, disabled surveys, rules, per-variant coverage, a rival without
a survey, and the fallback denominator.

After the fix and upstream integration, 74 affected backend tests pass in
38.26 s. These include online API, rival, browser/session, survey, failure,
patience and reading-time coverage. Strict Pyright and the backend import
smoke check pass. No frontend files change and no full test suite is run.
