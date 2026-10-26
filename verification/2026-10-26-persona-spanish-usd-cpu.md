# Fresh Spanish-description / USD customer-generation probes

Production `generate_batched` ran on Qwen3.5-2B Q4_K_M using the Spanish
customer description from `persona-us`, an Austin address, a USD 3–10 budget,
snacks/drinks categories and Monday 09:00–10:00 opening hours. The pipeline
performed trade-area profiling, traffic estimation and customer generation.
No responses were mocked or replayed. Backend code matched main `ede32886`.

| Output mode | Actual HTTP calls | Application cache hits | Written customers | Time |
| --- | ---: | ---: | ---: | ---: |
| Native JSON Schema | 3 | 0 | 1 | 31.69 s |
| Plain JSON | 3 | 0 | 2 | 64.95 s |

Actual wire modes were `json_schema` and `json_object`. Every generated
customer retained the 300–1,000 cent budget, listed product categories and
09:00 arrival. IDs were unique and the checked narrative fields contained
English text. The differing counts follow the model's traffic estimates:
the probe caps generation at two customers rather than requiring two.

This is evidence for the checked fields in these runs, not general semantic
accuracy. Manual inspection found model-authored background beyond the input
(for example, a hardware-store background in the native-mode profile).
No production prompt/schema change was made from these passing probes.
The server used five CPU threads, no GPU and an 8,192-token context. Server
prefix reuse was possible; these are not controlled speed measurements.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `persona-us-fresh/persona-us-json_schema-1793016134489102526`
- `persona-us-json-fresh/persona-us-json-1793016265194780723`
