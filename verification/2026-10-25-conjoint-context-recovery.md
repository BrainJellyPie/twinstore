# Recover oversized conjoint questionnaires without changing their design

A valid fifteen-task, four-option study with six Korean product attributes
generated 10,995 input-message tokens in JSON mode and 9,801 in JSON-schema
mode with the public Qwen3.5 tokenizer. Attribute levels were at most 41
characters, below the allowed 60. These counts exclude chat-template overhead
and already exceed the managed local model's 8K context before its 600-token
output budget. Previously each respondent failed as a whole.

Conjoint asking now catches only a typed input-context rejection, checking the
terminal failed attempt of Instructor wrappers. It bisects the existing tasks
and retries, recursively if necessary. Each child retains its original task
numbers, alternative profiles, product/persona context and distinct cache
identity. The shared request semaphore is released before children acquire it.
A one-task context failure, unrelated provider failure or invalid child answer
still fails the entire respondent; successful earlier tasks are not published
as a partial questionnaire. The normal fitting path retains one model call.

The complete result retains the original design and every choice. Optional
child explanations are joined in task order with exact duplicates removed,
without an additional model call. Presenting fewer tasks at once can affect a
real model's answers; recovery preserves the requested experiment and counts,
not a guarantee that split answers equal an unavailable full-context answer.

Thirty-two actual LiteLLM/Instructor HTTP cases cover both structured modes,
optional no-purchase choices, serial/concurrent execution, fitting requests and
three/eight/fifteen-task recursive recovery. They verify unchanged alternative
text/design, absolute task numbering, every choice and reason, estimation
matrices, no deadlock and repeat-cache reuse. Six controls cover irreducible
overflow, timeouts, unrelated errors, a later wrapped timeout and a failed
second child. Before the change, 25 tests failed and 13 controls passed in
4.08 seconds.

An additional token-counting HTTP probe used the full Korean questionnaire and
rejected inputs above 8,192 tokens. Recovery produced tasks 1–7 and 8–15 at
5,254/6,010 tokens in JSON mode and 4,638/5,306 in JSON-schema mode, retaining all
fifteen choices. Tokenizer SHA-256:
5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42.

The focused conjoint, choice-spelling, estimation and optional-reason suite
passed 420 tests in 7.66 seconds with two existing LiteLLM logging cleanup
warnings. Full source Pyright reported zero errors and warnings. The provider
responses and context limits are scripted; no native inference, weight
downloads or paid calls ran.
