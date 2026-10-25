# Recover oversized interview and study-theme requests

Study reading sends up to 160 answers of 300 characters to theme coding.
Using an ordinary 281-character English purchase explanation with a numbered
visit suffix, that input measured 10,874 Qwen3.5 tokens before chat framing or
completion space. Managed local plans use an 8,192-token context. The rejected
theme request prevented study commentary from being written; group interviews
could retain their answers but lose their themes. The tokenizer was the already
downloaded Qwen3.5 tokenizer, SHA-256
`5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`.

Only a recognized context rejection now splits the answers into two smaller
requests, recursively if necessary. Their theme labels and respondent counts
are reconciled in a compact request. Original answer order and multiplicity
remain intact, even when identical batches reuse a cache entry. Other is not
sent for reinterpretation. Missing or invalid merge indices retain the existing
Other fallback. The six-theme limit is applied once, after recovery, using
global respondent counts rather than the number of batches or labels.

Requests that fit retain the original single coding call. An individual answer
that still cannot fit, unrelated provider errors, or a failed reconciliation
propagate normally; no partial reading is returned. The split path adds model
calls only after overflow and may produce different theme wording or groupings
from a single large-context call. It does not shorten, deduplicate or resample
the selected answers. Existing limits selecting the first 160 nonblank study
reasons remain unchanged.

Eight actual LiteLLM/Instructor HTTP cases cover both JSON modes, 8/17/160
answers, nested splitting, odd-sized batches, a request that already fits,
repeated responses, explicit Other, per-group counts, cache reuse and the final
study commentary. Eleven boundary cases check direct/wrapped errors, an
irreducible answer, identical or unclassified themes, missing merge indices,
and a theme that is rare locally but largest globally.

The initial twelve-case regression failed six overflow cases and passed six
controls in 4.61 seconds. During development, an assertion was corrected to
allow identical batches to share a cached request; the respondent totals were
already preserved. The final focused suite passed 98 tests in 8.36 seconds;
full source Pyright reported zero errors and warnings. It emitted 27 known
LiteLLM asynchronous logging cleanup warnings. HTTP responses and context
rejections are scripted; no native model inference, downloads or paid calls
ran, and semantic quality on actual model output was not measured.
