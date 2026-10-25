# Online analyst: real CPU output and report evidence

Date: 2026-10-25. Integrates online-analyst work through upstream commit
`4f0de89891709c4700eb0419bbc4e4c7a890dea1` into the current bug-fix main.

## Actual failure

Qwen3.5-0.8B Q4_K_M ran under llama.cpp b11878 on five CPU threads, without GPU
offload, with an 8,192-token context. Calls used the production LiteLLM/Instructor
path, JSON Schema mode, temperature 0.2, seed 0 and the application's 1,600-token
answer budget. No remote paid model or canned model response was used for these
probes.

Eight deterministic rule shoppers generated a real report for two fashion stores.
The variant enabled quick add **and** removed the welcome popup; this fixture does
not isolate the causal effect of quick add. The report measured 25% control
conversion and 12.5% variant conversion; the paired interval included zero.

Before the fix, asking for exact real-world sales uplift next year produced a
33.3% forecast and $91.97, with an empty evidence list, in one call (5.96 s).
Valid JSON was accepted even though the answer had no supporting report figures.
An initial strict verbatim-copy check also rejected a correct comparison because
the tiny model rewrote the source lines. Short source IDs were tried but did not
reliably preserve the answer's meaning. They are not the shipped protocol.

## Changes

- Online numerical answers need at least one complete verifiable report line.
  The response schema requires `figures` and constrains its entries to actual
  source lines, with at most three citations. Runtime validation also protects
  JSON mode and cache reads. Invalid replies can use the existing bounded retry;
  exhausted failures do not enter the cache or persisted conversation.
- Duplicate citations are removed. Follow-up questions have a 200-character
  limit, addressing a real run that repeated a sentence until the 1,600-token
  output budget was exhausted twice (98.58 s total).
- Overall conversion is separate from revenue and engagement. Segment counts
  and rates have explicit labels. Each paired metric has its own source line;
  code labels intervals containing zero, including zero endpoints, as unclear.
  Missing intervals are identified instead of implying certainty.
- The online prompt explicitly says a simulation cannot forecast future
  real-world sales. The physical analyst retains its existing evidence policy.

## Findings and limits

The final forecast probe declined to predict future real-world sales in one call
(6.58 s). The
comparison probe could quote both overall rates and recognize the interval
including zero, but still described a purchase-segment decline from 66.7% to
33.3% as a significant improvement. That is a remaining model interpretation
failure, not a successful analysis. The checked-in harness flags this contradiction.

Source membership is not a semantic fact checker: a model can cite a real line
and misinterpret it, or cite an unrelated line. These changes do not establish
the tiny model's statistical competence or the realism of synthetic shoppers.
The forecast wording also sometimes repeats an instruction from the prompt.

Reproduce with a running local CPU server:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case analyst-comparison
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case analyst-forecast
```

The harness saves the generated report, fact sheet, raw HTTP bodies (without
headers/keys) and checks of the answer. A nonzero comparison result preserves the
known remaining failure. Local investigation records are under
`/workspace/scratch/cpu-vlm-probe/online-analyst-*` and `analyst-*`.

## Focused verification

115 backend tests and 10 frontend tests passed. Coverage includes both structured
output modes, empty/null/invented/partial evidence, duplicate citations, overlong
follow-ups, bounded retries, stale cache rejection, persistence after failures,
zero-boundary intervals, question echoes, product identity and Ollama grammar.
Existing LiteLLM logging cleanup warnings remain. After a type-annotation correction,
the 27 evidence/API cases were rerun successfully. Strict backend type checking
passed with zero errors/warnings and backend boot passed. Frontend TypeScript,
changed-file lint and the production build (19.79 s) passed.
