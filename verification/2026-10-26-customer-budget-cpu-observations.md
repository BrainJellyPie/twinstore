# A supplied customer budget can still disappear in valid model output

2026-10-26, main `15393c00`, Qwen3.5-2B Q4_K_M with its F16 vision
projector, llama.cpp b11878 on CPU (five threads, no GPU layers, 8K context).
These are real local model calls through the production customer pipeline.
Customer generation is text-only; loading a vision-capable model does not
make this an image interpretation check.

A French cafe case with a EUR 2.50–7.75 per-visit budget completed all three
stages in 49.11 s / three HTTP calls, with no application cache hits. Both
independently written profiles retained 250–775 stored money units and valid
category labels. Automated checks passed, but manual review found a morning
visitor described as shopping after a long day. This is not proof of full
semantic correctness.

A Japanese cafe case supplied Japanese category labels, `コーヒー` and `パン`,
and a per-person JPY 500–1,500 budget. Three calls took 54.19 s. Both category
labels were copied correctly. The second customer's explicit model output
instead set both budget fields to `"0"`, which the application validly
interprets as unspecified, despite the source supplying a range. The probe
failed its budget check. This is an unresolved model grounding problem; the
response was not malformed JSON and no category mismatch was observed.

A scratch-only prompt revision explicitly applied the range to EVERY
customer and allowed zero only when no applicable source budget existed.
It still produced 500–1,500 for the first person and 0–0 for the second.
A fresh three-call experiment took 55.58 s. That experiment accidentally
copied the parent artifact directory rather than its cache subdirectory,
so it had zero cache hits and is not a controlled upstream replay. A second
run copied the correct cache: two upstream hits and one fresh customer call,
17.03 s total, with the same budget failure. The prompt revision is withheld.
No budget was guessed, overwritten, or extracted with a language-specific
number regex to make these results appear successful.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `persona-fractional-json_schema-1792991326267156514`
- `persona-local-categories-json_schema-1792991480782226950`
- `every-budget-persona-local-categories-json_schema-1792991681834901384`
- `every-budget-persona-local-categories-json_schema-1792991745657886691`

The committed probe adds the Japanese-category case so the failure can be
rechecked with other models or future harness changes. Saved HTTP traces
include the actual generated values, not inferred schema defaults.
