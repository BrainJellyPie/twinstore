# Package identity survives catalog display order

2026-10-26, based on main `0d413856`. The package reader correctly transcribed
`LEAFY GREEN TEA 500 ml`, but a catalog entry named `Green Tea 500 ml — Leafy`
never reached the matching task. The evidence filter required the complete
catalog name as a contiguous phrase in the transcription. Moving a printed
brand to the end of a display name therefore discarded a supported candidate.

The filter now also permits reordering observed full tokens. It preserves
repeated-word counts and binds numbers to their following unit, so words from
`500 g / 100 ml` cannot be recombined into `500 ml`. Existing contiguous matches
remain supported. This only admits candidates to the separate model matching
step; it never selects a product without that model decision. Unknown words,
flavours, sizes and partial-word/CJK substrings stay excluded. The 150-candidate
cap still applies after filtering the entire catalog. Existing identity,
ambiguous-prefix and application SKU checks remain in place.

The first scratch implementation treated all words independently. Two added
mixed-quantity cases failed because it admitted recombined sizes; that version
was tightened before publication. The final 13-case suite passes (0.31 s):
brand/size order, label reading order, fullwidth text, wrong flavour/value/unit,
repeated words, mixed quantities and partial English/CJK words. Before the first
fix, four positive cases failed and six controls passed (0.29 s). A first shell
invocation used the wrong working-directory prefix and ran no tests; it is not
counted as a product failure.

## Actual CPU evidence

Qwen3.5-2B Q4_K_M, F16 vision projector, llama.cpp b11878, five CPU threads,
8192-token context, temperature/seed zero and thinking disabled. Actual production
`read_pack` calls use fresh application caches, with no model replies mocked.
Artifacts below are under `/workspace/scratch/cpu-vlm-probe-2b/`. These are warm
server timings, not speed comparisons or broad accuracy estimates.

| Artifact | Calls | Seconds | Result |
| --- | ---: | ---: | --- |
| Before: `pack-brand-suffix-json_schema-1793003091843368402` | 1 | 16.63 | Correct transcription, empty shelf link; matching never called |
| Initial candidate filter: `pack-brand-suffix-json_schema-1793003225583166472` | 2 | 5.01 | Correct reordered catalog name selected |
| Final filter: `final-order/pack-brand-suffix-json_schema-1793003412006650462` | 2 | 5.62 | Correct reordered catalog name selected |
| `pack-wrong-variant-json_schema-1793003233392838436` | 1 | 2.81 | No link to the wrong flavour or size |
| `pack-blank-json_schema-1793003239204556082` | 1 | 13.24 | No invented label metadata or catalog link |
| Final filter: `final-order/pack-mixed-quantities-json_schema-1793003481991379950` | 1 | 15.62 | Reads `NET 500 g SERVING 100 ml`; rejects both offered wrong products (500 ml / 100 g) before matching |

The wrong-variant and blank controls were run after the first candidate filter;
the final tightening only restricts newly reordered matches. The final positive
and mixed-quantity cases were then rerun against the final code. Every listed
run has zero application cache hits. The diagnostic now includes reusable
`pack-brand-suffix` and `pack-mixed-quantities` cases.

The mixed-quantity image was inspected directly: a synthetic 600×800 package
with LEAFY, GREEN TEA, NET 500 g and SERVING 100 ml printed on its label. This
is a deterministic fixture, not a real package photograph. In the suffix case,
the model still leaves the separate brand field empty and includes Leafy in the
name despite reading the word correctly. The passing check is the catalog link,
not a claim that every metadata field is ideal. Those model values are retained.

## Other evidence and integration

The same loop's full physical-visit CPU results and withheld prompt/image
experiments are in [physical visits](2026-10-26-physical-visits-2b-cpu.md).
The visit probe now accepts an explicit loopback endpoint and retains requests
and images before HTTP completion, including failed attempts. No physical
shopper prompt, schema or default image setting was changed.

Integrated upstream through `44b7a9eb`: readable phone reports, correctly sized
A/B and operations inputs, product-picker names, singular search results, a
stable online browsing pane, and keyboard focus restoration after navigation.
The changelog conflict was only a duplicated/moved deletion entry; it was kept
once while preserving all new changes.

Verification: 244 selected backend cases pass in 8.97 seconds (14 existing
LiteLLM asynchronous-logging warnings), and 64 selected frontend cases pass in
13.33 seconds (chart-dimension warnings in jsdom). Strict backend Pyright has
zero errors/warnings and the backend boots. Changed-source ESLint has no
errors/warnings; TypeScript and the production build pass (20.74 seconds), with
the usual bundle-size and plugin-time warnings. Both changed probes compile
and whitespace checks pass. No full repository suite was repeated.
