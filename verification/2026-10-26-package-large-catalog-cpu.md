# Find observed packages beyond the first 150 catalog names

2026-10-26, based on main `502a62f9`. The actual Qwen3.5-2B Q4_K_M CPU
vision model correctly transcribed `LEAFY GREEN TEA 500 ml` from a drawn
600×800 test package. The label was inspected directly. This is a deterministic
label fixture, not a real-world product photograph. The catalog contained
180 unrelated names followed by the matching 500 ml green tea and two wrong
variants (1 L green tea and 500 ml black tea).

The original reader returned no product link even though the complete name
was present in the model's transcribed evidence. It took one actual image
call, 14.48 s total. The cause was deterministic: `read_pack` limited the
catalog to its first 150 unique names before checking which names were
supported by the image text. The matching product at position 181 was never
considered, and the matching model was never called.

The reader now filters all unique catalog names against the observed text,
then limits the supported candidates sent to the matching model to 150.
The vision observation still receives no catalog names. Exact observed
words, variant/size checks, bounded name handling and ambiguity protections
remain in place; no unsupported product is added as a candidate.

A controlled after-run copied the original observation cache, then made one
new matching-model call (1.969 s; 2.14 s total). It sent only the supported
`Leafy Green Tea 500 ml` candidate and returned the correct full name. The
observation was not regenerated or modified to get that result.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- Before: `pack-large-catalog-json_schema-1792994809182946260`
- Cached observation + fresh match: `pack-large-catalog-json_schema-1792995011783133806`

Nine regressions cover both JSON modes, positions 1/150/151/5000, cache
reuse, catalog reordering, removing the observed product, wrong variants,
and preserving the candidate limit after filtering. Before the fix, five
failed and four passed. The pre-fix run emitted three LiteLLM logging-worker
coroutine warnings.

A separate actual CPU blank-image control returned empty name/brand/size/
category/product and confidence zero in 14.66 s. That result passed; no
blank-image application change was made. Artifact:
`pack-blank-json_schema-1792994666504727599`.

A fresh application-cache run also passed: two actual HTTP calls, zero
application cache hits, 3.52 s total, artifact
`pack-large-catalog-json_schema-1792995077429134684`. Server prompt reuse
can affect these timings; this is correctness evidence, not a speed benchmark.

The integration includes `a00990dd` from `claude/blissful-rubin-tgy6gh`,
which changes default online arrivals to 16% direct, 58% search, 25% social
and 1% email in both API and UI. The scan regression previously required all
four channels to appear in a 40-person sample; that assumption is invalid
with 1% email traffic. It now compares the full scan panel against ordinary
run defaults, while retaining the paired-visit equality check.

Validation: 156 affected backend cases initially passed; the one outdated
arrival-mix assertion was corrected and both scan tests then passed on rerun
(157 distinct selected cases with passing results). Fourteen LiteLLM logging
coroutine warnings appeared. Strict Pyright and backend boot passed. All 32
selected RunLauncher UI tests passed, and the frontend production build and
RunLauncher ESLint check passed. The package-manager wrapper initially tried
to reinstall dependencies and stopped on ignored dependency build scripts;
the installed local binaries successfully ran the same TypeScript/Vite build
commands and tests. Its generated workspace-config edits were removed. Vite
reported its usual chunk-size/plugin-timing warnings. No full repository
suite was run.
