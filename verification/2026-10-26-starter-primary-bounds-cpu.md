# Bound valid starter selections before repeating the request

2026-10-26, based on main `6e4bfb68`. Actual local CPU model:
Qwen3.5-0.8B Q4_K_M with F16 vision projector, llama.cpp b11878,
five CPU threads and an 8K context. Artifacts are retained under
`/workspace/scratch/cpu-vlm-probe`. These measurements use actual model
responses; test fixtures below are separate from inference.

## Actual failure path

`cafe-json-1792984470903610610` uses the production automatic starter flow
with a Japanese cafe description, JPY prices, no alcohol and one product per
category. The first request correctly assigns all ten sections to nine
categories. The second returns every catalog product in those categories,
8–16 each, despite the limit of one. Every ID is valid and distinct within
its category.

The primary response was rejected for its count. A full correction request
then exceeded the 8192-token context at 8540 tokens and returned HTTP 400
twice. Nine individual category requests followed. Each again returned all
its valid IDs, which the existing small-task validator limited to the first
requested product. The run ultimately succeeded, but took 13 HTTP calls
and 119.45 s. The original response already contained those final selections.

## Fix

Apply the existing small product task's bounded-subset behavior to primary
product groups before field length validation and caching. Normalize model
codes and legacy catalog SKUs, check the **entire** list against that
category, reject duplicates after normalization, and only then retain its
first requested products in model order. The bound includes both the owner's
category limit and available shelf capacity.

Unknown IDs, wrong-category IDs and duplicate IDs in the discarded tail
remain errors and trigger normal recovery. Empty or malformed lists, missing
categories and duplicate categories remain invalid. No rack assignments,
catalog products, prices or additional model choices are invented. The
prompt and response schema are unchanged.

An explicit replay of the saved pre-fix cache,
`cafe-json-1792984749287801498`, now uses two cache hits and zero HTTP calls
in 0.01 s. Its final selections and complete stored layout exactly match the
13-call baseline. This is cache validation, not fresh model inference.
`local-model-probe.py --cache-from` copies the source cache to a new artifact
and records the source; normal runs still start with fresh application caches.

A fresh post-fix CPU run, `cafe-json-1792984844329792565`, takes two actual
HTTP calls, zero application-cache hits and 68.84 s (22.622 s for categories,
46.073 s for products). It produces the same final selections as the baseline,
excludes alcohol and keeps one product per category. No correction or small
product task is needed. The server's prompt cache is warm, so times are
observations rather than controlled latency benchmarks; the 13-to-2 HTTP
call reduction is directly recorded.

## Other actual CPU boundaries

- `pack-wrong-variant-json_schema-1792984414084970530`: the vision model
  reads a drawn green-tea 500 ml label, with only black-tea or 1 L catalog
  candidates. One HTTP call, 7.57 s; no incorrect product link.
- `pack-label-json-1792984436523780987`: JSON-mode vision observation and
  text matching identify the supported green-tea 500 ml product. Two HTTP
  calls, 9.93 s. The input is a deterministic test label, not a photograph.

These package checks revealed no new linking failure. They do not establish
general OCR accuracy. The starter fix enforces valid IDs, counts and coverage;
it does not establish that the tiny model's assortment is commercially ideal.

## Focused checks

The ten new regressions fail before the fix. They cover raw/code identifiers,
category and shelf limits, invalid/duplicate/wrong-category tail IDs,
retaining other valid categories, canonical cached results and cache reuse.
Existing over-limit expectations now assert the bounded valid subset;
persistent invalid choices still fail without changing the original store.
After the change, 616 affected backend tests pass in 8.93 s. No frontend
files change and no full test suite is run.
Strict Pyright reports zero errors/warnings, the backend import smoke passes,
and probe syntax and whitespace checks pass.
