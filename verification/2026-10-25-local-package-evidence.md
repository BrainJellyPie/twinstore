# Package reading tested with an actual small CPU VLM

## Observed failures

Qwen3.5-0.8B Q4_K_M plus its F16 projector, llama.cpp b11878, CPU only/five threads,
8192 context, one slot, temperature/seed zero, thinking disabled, JSON Schema.
The original production reader failed twice on a bundled, unlabelled strawberry-jam
image because it emitted `confidence: 100` despite the schema's 0–1 numeric range.
Numeric range keywords alone did not constrain this llama.cpp generation.

Prompt-only/enum-only experiments removed that range error but exposed incorrect
metadata and links. The model copied the supplied catalog list into supposed
`printed_text`, invented jar sizes, and selected a 340 g SKU absent from the image.
Reading the image separately exposed a further failure: a text matcher chose a
1 L product for a clearly printed 500 ml label when the exact variant was absent.
These were actual HTTP replies, not mocked SDK responses.

## Implementation

- The image call receives **no catalog candidates**. Its first schema field is
  `printed_text`; the tiny model's observations improved when transcription came
  before inferred metadata. The generated schema requests all observation fields.
- Confidence has explicit fractional instructions and a small enum for constrained
  decoding. Validation still rejects values outside 0–1; percentages are not silently
  converted. Valid fractional replies from other providers remain accepted.
- Brand and size must occur in the transcribed words. Unreadable/null label text
  cannot authorize guessed metadata or a product link.
- Only catalog names supported by the transcribed words reach a separate text
  matching call. Word boundaries prevent substring matches such as `Cream` inside
  `ICECREAM`; NFKC, case/punctuation and digit/unit spacing handle `５００ｍｌ` / `500 ml`.
  The returned match is checked against those supported candidates even when a
  provider ignores the JSON-schema enum. Global ambiguous-prefix and unique-SKU
  safeguards still apply.
- Image observations can be cached across catalogs. Matching remains catalog-specific;
  switching to a catalog containing only wrong variants cannot reuse a previous link.

This intentionally makes automatic linking conservative. OCR errors, translated
catalog names, reordered names or equivalent sizes written differently can leave
the link empty; manual linking remains available. The small model can still produce
imperfect visual names (for example `unknown` for a blank image). This change does not
claim to make its visual understanding or confidence calibration reliable.

## Actual production harness results

The checked-in harness ran the final production code with the application's 400-token
package output budget, a fresh application cache per case, and real model calls.
Inputs were the bundled unlabelled jam, a deterministic synthetic `LEAFY / GREEN TEA /
500 ml` label, the same label with only 1 L/black-tea candidates, and a white image.

| Case | Calls | Elapsed | Result |
| --- | ---: | ---: | --- |
| Unlabelled jam | 1 | 5.75 s | Visual name retained; brand, size and product link empty |
| Readable label | 2 | 7.52 s | Linked `Leafy Green Tea 500 ml` |
| Only wrong variants available | 1 | 2.26 s | Correctly left product link empty |
| Blank image | 1 | 1.05 s | No brand, size or product link |

The readable-label case uses one image observation and one text matching call.
Cases without supported candidates skip matching. Timings are single observations;
server prompt caching affects them. Raw requests/replies and input images are in
`/workspace/scratch/cpu-vlm-probe/pack-production-harness/`.

Reproduce against a running CPU local server:

```sh
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case pack-jam
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case pack-label
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case pack-wrong-variant
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case pack-blank
```

The harness checks expected link/evidence behavior and retains `image.png`,
`http.jsonl` and `result.json`. Image base64 is replaced by a file reference in the
trace; request headers and API keys are never recorded. The labelled positive control
is a generated test fixture, not a claim of accuracy on real-world package photos.

## Focused regression validation

- 143 tests passed in 7.84 seconds: real SDK parsing with controlled HTTP replies,
  observation/catalog separation, schema order and fractional confidence, unsupported
  size/variant rejection, null/optional metadata, fullwidth labels, partial-word
  rejection, malicious out-of-enum matches, bounded/ambiguous names, unique linking,
  concurrent package edits, lifecycle deletion and API failures.
- The 22 evidence cases were rerun after adding cross-catalog cache assertions.
- Full backend source Pyright: zero errors/warnings. Backend server import passed.
- Known LiteLLM asynchronous logging warnings appeared in the focused tests.
  No frontend or full-repository suite was run for this backend/harness change.
