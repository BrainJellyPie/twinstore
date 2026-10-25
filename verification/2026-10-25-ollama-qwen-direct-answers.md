# Native Ollama Qwen3.5 answer budgets

The recommended Ollama model is `qwen3.5:2b`. Its official registry manifest
uses renderer `qwen3.5`; Ollama v0.40.11 registers that renderer with thinking
enabled by default and advertises both boolean thinking values. TwinStore sent
no native `think` override, so a short automatic decision could spend its output
budget on reasoning before returning final content.

Sources inspected on 2026-10-25:

- [Official 2b manifest](https://registry.ollama.ai/v2/library/qwen3.5/manifests/2b),
  config blob `sha256:0f7af3a2d4145d7e4dbc9dbab778ac7a6aee7104fb93570c047726b5a816781f`.
- [Renderer registration](https://github.com/ollama/ollama/blob/v0.40.11/model/renderers/renderer.go),
  blob `df7fb9674fafbe934efc9a3a32eb902155a392d2`.
- [Qwen3.5 renderer and supported thinking values](https://github.com/ollama/ollama/blob/v0.40.11/model/renderers/qwen35.go),
  blob `f55e1905ef4287e59044c0fb89a8326f2f19f304`.
- [Default thinking resolution](https://github.com/ollama/ollama/blob/v0.40.11/model/renderers/thinking.go).

Native requests now send `think: false` at the top level for the official
`qwen3.5`, `library/qwen3.5` and `registry.ollama.ai/library/qwen3.5` names.
Cloud tags and the official cloud endpoint are excluded. Other families,
custom namespaces and similarly named models retain their prior behavior.
The output ceiling, input-preservation and context-shift controls are retained.
Only the changed thinking policy receives an additional cache identity field.

A scripted native HTTP response models reasoning exhausting a 160-token budget
unless the explicit switch reaches the server. The actual LiteLLM/Instructor
path reproduced 35 failures with 11 passing controls in 4.30 seconds before
repair. All 195 focused native-output, context, schema and template-policy tests
passed in 4.30 seconds afterward, with 73 existing LiteLLM logging coroutine
warnings. Full-source Pyright reported zero errors and warnings.

Coverage includes text/image and synchronous/asynchronous calls, both JSON
modes, local and LAN endpoints, official model-name forms, cloud/custom/other
model controls and old-policy cache separation. This checks protocol behavior;
no native inference speed or model answer-accuracy measurement is claimed.
