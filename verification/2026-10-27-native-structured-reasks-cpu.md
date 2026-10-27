# Concise local JSON Schema corrections

The preceding customer-row experiment exposed an avoidable source of long
native-schema retries. Instructor repeated complete previous response
objects, transport metadata and prior errors inside each correction, even
though the original assistant replies were already present in the message
history. The third request contained 7,025 prompt tokens in an 8,192-token
local context. Its last correction message alone was 10,492 characters.

The client now applies its existing concise-correction hook to **both**
plain JSON and JSON Schema requests on loopback endpoints. It keeps the
current validation error, all original response messages, images, initial
instructions and earlier correction history. It removes only the redundant
SDK dump inside the newly appended correction message. Remote endpoints,
the initial request, transmitted schema, retry count, parser, cache
identity and usage accounting are unchanged.

## Actual CPU comparison

One new fresh run made **two actual HTTP calls** using Qwen3.5-2B Q4_K_M,
llama.cpp b11878, five CPU threads, no GPU, 8,192 context, reasoning off,
temperature **1**, and no application cache hits. The reference is the
already recorded final five-person run from
`2026-10-27-customer-request-types-cpu.md`; its three calls are not new
inference for this change. No reply was mocked or replayed.

The complete first request **and response content are exactly equal** to
the reference. Both first responses assign two customers the wrong types,
so both runs exercise the same row-type correction.

| Measurement | Previous run | Concise native correction |
| --- | ---: | ---: |
| First request prompt tokens | 783 | 783 |
| Second request prompt tokens | 3,093 | 1,752 |
| Second correction text characters | 5,506 | 702 |
| Third request prompt tokens | 7,025 | No third request needed |
| HTTP calls | 3 | 2 |
| Probe duration | 158.75 s | 78.43 s |

The second input is **43.4% smaller** in reported prompt tokens. In this
specific comparison, all five customer identities match their requested
rows after the second response instead of the third. The call/time change
is an observation from one fixture, not a general latency or model-quality
guarantee. Total prompt-token usage also changes because one call is avoided;
do not attribute that entire difference solely to text compaction.

The overall probe remains a failure: two generated budgets are
KRW 2,000–5,000 despite the supplied 3,000–10,000 range. The previous run
also violated that range. This change reduces redundant correction input;
it does not solve budget interpretation or other documented semantic
limitations. This was a text request to the local VLM, not a new vision test.

Reproduce using `verification/local-model-probe.py --case
persona-nightmarket-five --temperature 1 --structured-output json_schema
--endpoint http://127.0.0.1:8082/v1`. Local evidence:

- Reference: `/workspace/scratch/persona-row-types-ordered/persona-nightmarket-five-json_schema-1793065867332183993/`.
- New run: `/workspace/scratch/native-concise-reasks-cpu/persona-nightmarket-five-json_schema-1793066626905674423/`.
- Comparison: `/workspace/scratch/native-concise-reasks-reproduction.json`.

## Verification

Extending the existing reask tests to require concise local native
corrections reproduced **16 failures and 48 passes** before the fix (7.32 s).
After the change, all **64 passed** in 3.13 s. The matrix covers both wire
modes, remote/loopback endpoints, sync/async text and image requests,
validation/duplicate-key failures, successful correction and bounded repeated
failure. It checks original responses and images, preserved user content,
exceptions, usage totals and canonical cache behavior. These mocked transport
tests are separate from the actual CPU calls above.

The final related run passed **318 tests across 11 files** in 10.87 s,
including retry usage, cache modes, schema compaction, duplicate keys,
provider fallback, context recovery and the customer-row guard. Its 13
warnings came from dependency/resource cleanup. Strict backend Pyright
returned zero errors/warnings; backend import smoke and diff checks passed.
The full repository suite was not repeated.

No frontend production code or published release files changed.
