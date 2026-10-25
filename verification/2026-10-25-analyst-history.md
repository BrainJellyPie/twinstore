# Leave room for an analyst's reply on a local CPU model

Date: 2026-10-25. Qwen3.5-0.8B Q4_K_M, llama.cpp b11878, five CPU threads,
no GPU offload, 8,192-token context. The production analyst used JSON Schema,
temperature 0.2, seed 0 and its normal 1,600-token reply budget.

## Actual reproduction

Eight rule shoppers visited four fashion-store variants, the API's maximum number
of compared stores. Their long Korean names describe the changed designs. Actual
rule-policy visits produced the summaries and paired comparisons. Four saved
question/answer exchanges added 8,400 Korean characters: questions within the
600-character API limit and answers within the 1,500-character response limit.

With the existing eight-message window, each model request consumed 8,086 prompt
tokens. Only 106 tokens remained in the local server's context. Both attempts
ended with `finish_reason=length` and an incomplete JSON response, after 41.77 s.
The report was 10,774 characters; this was a permitted comparison with ordinary
conversation lengths, not an oversized current question.

## Change

The shared physical/online analyst now keeps a contiguous suffix of at most eight
messages within a 4,000-byte allowance. A leading answer is removed if its question
does not fit. Oversized exchanges are omitted whole, with a short context note.
The complete report and complete latest question remain in the prompt. Short
conversations retain their previous prompt exactly, and the stored conversation
is never modified by this context selection.

The byte allowance reserves space; it is not a tokenizer-specific guarantee for
every model or arbitrarily large report. If an omitted exchange is needed, the
prompt asks the model to request clarification.

## Completion is not correctness

The checked-in `analyst-history` CPU probe completed in one call: 4,398 prompt
tokens, 616 reply tokens, 22.58 s. It recorded `completed=true` but `success=false`:
the model still invented next-year revenue, attaching an actual report header as
its evidence. The probe flags this unsupported forecast. This context fix does
not make source membership a semantic fact checker or establish the tiny model's
ability to interpret causal/statistical results.

An earlier bounded run declined the forecast but made an unsupported causal
claim. Both results remain available; the final failure was not replaced with
the more favorable response.

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case analyst-history
```

The harness saves the complete generated report, facts and raw HTTP bodies
without headers/keys. Investigation files are under
`/workspace/scratch/cpu-vlm-probe/online-analyst-unsupported-four-*`; the final
checked-in case is under `analyst-history-*`.

## Verification

82 focused backend tests passed, covering byte-boundary and multibyte histories,
complete exchanges, orphan answers, unchanged short prompts, full report/current
question retention, numerical evidence, cache revalidation, echoes and physical/
online analyst APIs. Existing LiteLLM logging cleanup warnings remain. Strict
backend type checking passed with zero errors/warnings, and backend boot passed.
No frontend source changed.
