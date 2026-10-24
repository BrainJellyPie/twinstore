# Use the same coordinates in grounding prompts and decoding

With the automatic convention, shelf grounding always asked for image pixels,
but the decoder treated Qwen 3 responses as normalized 0–1000 coordinates and
Gemini responses as y-first normalized coordinates. A model correctly following
the pixel prompt therefore produced shifted or shrunken product boxes. Explicit
Gemini mode also gave conflicting instructions: its prose said y-first while its
JSON example said x-first.

Resolve known model conventions before constructing the prompt, then pass that
same convention to decoding. Render the example's coordinate order consistently
with the request. Explicit user overrides remain authoritative, while unknown
aliases and Qwen 2.5 retain the existing automatic/pixel behavior.

Twenty offline contract cases use a model oracle that returns the same known,
asymmetric image region in exactly the units/order requested by the prompt. They
check coordinates after actual image resizing and decoding for portrait and
landscape images, Qwen 3 spellings, Gemini, Qwen 2.5, generic local aliases and
explicit pixel/normalized/y-first overrides. Refinement is intercepted so it
cannot hide a wrong coordinate conversion by dropping a misplaced box.

Before: ten failures and ten passing controls. After: 44 focused coordinate and
capture-pipeline checks passed in 4.15 seconds; one opt-in detector check was
skipped. Strict Pyright reported zero errors; `git diff --check` passed. This
verifies the prompt/decoder contract with an offline oracle, not live model
localization accuracy. No model weights were downloaded.
