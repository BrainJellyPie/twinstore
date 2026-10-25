# Online report and shopper tracking integration — 2026-10-26 KST

Integrated the latest online feature branch through 1aca40e3: report hero,
conversion and interval charts, shopper cards and stream, page flow, full-width
reports, and prominent physical-store shopper tracking. Preserved the current
main's editor write locks, resource identity keys, deletion cache cleanup and
welcome-discount correction. The changelog conflict retained both sets of notes.

Review reproduced an analytical error in the new busiest-route caption. Four
visits went home → product → cart, three search → product → checkout, and three
category → product → checkout. Greedily selecting the widest link at each step
displayed home → product → checkout, a journey nobody took. The UI regression
failed with exactly that nonexistent route (2.63s); five backend cases also failed
before the correction (0.68s).

Reports now count complete observed prefixes within the six-step chart horizon,
including the real final outcome. The frontend uses that saved route. Older
reports keep their charts and omit a route they do not contain. Tests cover
merged cohorts, reversed input order, empty/one-step visits, the chart horizon
and legacy results.

Verification: 43 focused backend tests passed in 38.23s; 112 frontend tests in
15 files passed in 24.42s. Full backend Pyright and boot passed. Frontend
TypeScript and ESLint on all 18 changed TS/TSX files passed; production build
passed in 19.58s with existing chunk-size/plugin-timing warnings. An initial
lint invocation selected no paths and ran repository-wide, reporting five
pre-existing no-undef errors in scripts/audit-i18n.mjs; the corrected scoped
invocation passed. These checks made no live model calls.

The user subsequently requested real CPU VLM probes. Qwen3.5-0.8B and llama.cpp
were prepared separately under /workspace/scratch/cpu-vlm-probe; real-model
observations will be reported separately from this integration's tests.
