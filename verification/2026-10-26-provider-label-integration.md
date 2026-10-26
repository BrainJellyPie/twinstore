# Integrate descriptive provider/model labels

Integrate `claude/online-shopping-features-ji7y0f` through
`ddbddba27c4bb91cdd3c0c17f6d2986b5f488e34`, retaining branch ancestry. The
new commit localizes descriptive local/self-hosted provider names and model
labels in settings, capture, run selection, interviews, marketing and online
tools. All six languages are supplied. Provider kinds, model references,
option values and settings mutation payloads remain unchanged. Brand names
and provider labels that differ from the known English source are preserved;
vLLM's descriptive served-name suffix is translated without changing its model
name. The labels agree with the server's current provider presets.

Changelog conflicts retain both branches' entries, including the new shopper
shelf-dependency fix. The entire `0.8.2` section and older notes remain
byte-identical. No release or tag is created by this integration.

Sixteen focused settings, model-selection, capture, marketing, online and
interview test files pass **207 tests in 18.05 seconds**. TypeScript passes;
ESLint on every changed TypeScript file reports no errors or warnings. Vite
builds in 20.77 seconds with existing plugin-time and chunk-size notices.
Diff checks pass. Backend code is unchanged and inherits 421's 471 distinct
focused cases, strict Pyright/boot checks, and its documented CPU-model
limitations. This display change is not a new inference-quality claim.

Logs, test paths and command timings: `/workspace/scratch/provider-labels-*`.
