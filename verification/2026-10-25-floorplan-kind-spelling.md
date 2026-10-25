# Preserve vision geometry for known fixture-kind spellings

A fixture kind such as `Fridge`, `Gondola`, or padded uppercase `ENTRANCE`
rejected a complete model reading. Explicit vision import failed; automatic
import instead used the classic geometry reader, discarding the model's
scale, fixture classifications and labels. The model-only fixture schema now
trims and case-folds known kind strings before literal and geometry validation.
The prompt requests the exact lowercase values. Unknown kinds, synonyms and
wrong types remain invalid, and domain fixture inputs are unchanged.

Real LiteLLM/Instructor HTTP tests cover all six kinds in both structured-output
modes with Unicode surrounding whitespace. They verify the outline, relative
fixture coordinates, unchanged label text, scale, complete generated stock/layout,
layout validity and cache reuse against the canonical expected reading.
Boundary controls preserve the distinction between a zero-area entrance on
the outline and a shelf/counter requiring positive area. Scripted-model API
tests cover both automatic and explicit vision imports: the supplied 20-by-10
metre plan remains the 16-by-8 saved layout and active setup, without fallback.

The initial focused reproduction had 20 failures, nine passes and eight
deselections in 4.87 seconds. Five failures were geometry-message controls
that encountered the kind error before reaching the intended positive-area
check; they are not additional production defects. After the repair, focused
kind, metadata, geometry, overlap, required-fixture and import-API suites passed
189 checks in 9.49 seconds, with 35 known LiteLLM logging-cleanup warnings.
Full source Pyright reported zero errors and warnings. No native inference,
model weights or paid calls were used; response frequency was not measured.
