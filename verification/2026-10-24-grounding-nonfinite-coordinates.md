# Reject nonfinite grounding coordinates before normalization

Grounding accepted NaN and infinite coordinates. Image clipping then turned them
into apparently valid edge coordinates: `[100, 50, NaN, 250]` on an 800×600 image
became `[100, 50, 800, 250]`. This could crop or group the wrong product rather than
identify an invalid model answer, and the raw response had already been cached.

Require finite values for every coordinate before caching, state that constraint
in the prompt, and allow one structured-response correction. Repeated invalid
output returns the existing no-detections fallback so the capture pipeline can
use its classic detector. Valid coordinates retain their existing conventions,
clipping and geometric refinement.

Twenty-four offline HTTP regressions cover all four positions, NaN and signed
infinities, with a corrected second answer or repeated invalid output. They use
real OpenAI transport, LiteLLM, Instructor, image encoding, coordinate conversion
and caching. Corrected boxes retain their exact pixel region and are reusable;
bad boxes never reach refinement or the cache. No additional model calls occur
after the two-attempt budget.

Before: all 24 regressions failed. After: 68 focused grounding and capture checks
passed in 6.62 seconds, with one opt-in Grounding DINO test skipped. Strict
Pyright reported zero errors; `git diff --check` passed. No live inference or model
downloads were used.
