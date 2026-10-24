# Let multi-fixture floor-plan responses finish

The application limited the complete floor-plan response to 1,500 output
tokens. A valid 40-fixture response with ordinary JSON indentation needs about
2,400 Qwen3.5 tokens; an 80-fixture response needs about 4,800. Truncation made
explicit VLM import fail, while automatic import switched to classic geometry
and lost the model's fixture kinds and category labels.

Raise this reader's existing per-task ceiling to 6,144 tokens. The input image,
coordinate validation, physical-scale handling, two-attempt limit and failure
behavior are unchanged. The source capture configuration is copied and retains
its own 320-token product-reading ceiling.

With the existing Qwen3.5 tokenizer, compact/indented fixture responses measured:

| Fixtures | English labels | Korean labels |
| --- | --- | --- |
| 8 | 229 / 519 | 237 / 527 |
| 40 | 1,085 / 2,399 | 1,125 / 2,439 |
| 80 | 2,155 / 4,749 | 2,235 / 4,829 |

Tokenizer SHA-256: `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`.
The ceiling covers these measured plans; server context and unusually long
responses can still limit larger plans.

Before the fix, 24 application/HTTP cases failed while 26 smaller-output and
failure-handling controls passed in 5.66 seconds. Both JSON modes and auto/VLM
reader choices exercise the real LiteLLM/Instructor path. A scripted server
truncates according to the measured response size and actual request cap. Tests
require every coordinate, label and physical dimension to survive and identical
reads to use cache. The test photo has a visible outline, so automatic fallback
is also exercised on an image the classic reader can read.

The focused output, geometry, aspect, overlap, metadata and API suite passed all
219 checks in 7.40 seconds. Full source Pyright reported zero errors and warnings.
The 85 warnings were existing LiteLLM async logging cleanup warnings. No native
inference, model downloads or paid requests ran.
