# Preserve the loaded grounding model's coordinate convention

TwinStore starts its managed vision model with the API alias `local-model`.
Shelf grounding used that alias to select coordinate units, hiding the known
Qwen3.5 family from the existing Qwen prompt and decoder. With an 800 × 400
photo, the normalised box [125, 100, 375, 300] was treated as pixels after resizing:
it mapped to approximately [130.2, 104.2, 390.6, 312.5] instead of [100, 40, 300,
120]. All four coordinates fit inside the resized image, so the overflow
heuristic could not recover the intended units.

The application now passes the loaded model key to the detector when the
client has a managed cache identity and the ready, managed runtime has a model
plan at the same API endpoint. The request still uses `local-model`; the model
hint only selects the existing grounding convention. External endpoints, a
different port or host spelling, missing plans and stopped runtimes cannot
supply this hint. Endpoint trailing slashes remain equivalent. LFM2.5 keeps
the generic pixel convention.

Twenty actual LiteLLM/Instructor HTTP cases cover all four managed Qwen3.5
models and LFM2.5, both JSON modes, landscape and portrait photos, resizing,
the request model alias, coordinate prompts and repeated cache use. Eight
metadata boundary cases check when the hint is eligible. After correcting
the test adapter's initialisation order, the unchanged implementation failed
17 cases and passed 11 in 2.90 seconds. The focused grounding, coordinate,
output-budget, required-list, cache-identity and endpoint suite passed 178
tests in 5.65 seconds. Full source Pyright reported zero errors and warnings.

HTTP answers are scripted; these checks establish the alias/wiring defect,
not a measured frequency of real-model instruction failures. No native model
inference, model downloads or paid calls ran. The suite emitted 25 known
LiteLLM asynchronous logging cleanup warnings.
