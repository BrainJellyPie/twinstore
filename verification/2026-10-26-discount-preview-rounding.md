# Discount previews and percentage bounds

The actual CPU model drafted two 50% discounts for Tea, whose regular price
was 101 cents and current selling price was 81 cents. Production application
correctly used 50 cents for the regular-price basis and 40 cents for the
current-price basis. The A/B editor on parent `480d6f4f` instead displayed
51 and 41 cents: JavaScript rounds an exact positive half upward while both
Python store engines use ties-to-even rounding.

The editor now follows that existing engine policy. The engine's monetary
calculation is unchanged. The preview also disappears for invalid percentages.
The editor rejects discounts below −100% or at/above zero, and category
changes outside the API's −100% to 300% interval. Fractional percentages
remain usable. Invalid fields explain their range in all six languages and
associate the explanation with the input; correcting the value restores Run.

## Evidence

The CPU probe used Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads,
8,192-token context, no GPU, reasoning disabled and native JSON schema.
It completed in 14.14 seconds with one HTTP request and no application cache
hit. Both discount bases, retained 101-cent reference, unrelated Water and
unchanged source store passed. This drafts text and applies the resulting
operations; it does not simulate shoppers or exercise image recognition.

Result: `/workspace/scratch/cpu-vlm-probe-2b/discount-rounding/ab-rounding-discount-json_schema-1793037871249038704/result.json`.
The reusable A/B probe includes `rounding-discount` for this case. No extra
model inference was needed after the UI fix because backend and prompts are
unchanged; UI assertions compare to the prices observed in this run.

The extended UI regression file fails 14 cases and passes 28 against the
parent implementation. After repair, 131 distinct frontend cases pass:
118 across five relevant marketing files, then 55 in the extended discount
file and catalog ownership check (42 overlap). They include both rounding
directions, fractions, zero, missing references, USD/KRW/JPY, editing invalid
values back into range, valid endpoints, all six localized corrections and
existing model-draft acceptance/serialization. These are jsdom checks, not
a manual browser or physical-device run.

Backend verification passes 41 focused cases, including 24 new rounding
controls that compare physical and online application and source immutability.
Three existing LiteLLM logging cleanup warnings remain. Strict Pyright has
zero errors/warnings; server import, TypeScript and changed-file ESLint pass.
Production build passes in 22.73 seconds with the existing chunk-size and
Babel plugin timing notices. The release tag and assets remain v0.8.2;
this change is recorded under Unreleased.

Logs: `/workspace/scratch/discount-rounding-{cpu,before,ui,ui-final,backend,boot,pyright,tsc,eslint,build}.log`.
