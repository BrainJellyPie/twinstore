# Preserve usable context in managed local servers

TwinStore starts llama.cpp with `-c` and `-np`, without enabling unified KV. In
llama.cpp's default non-unified mode, context per sequence is the total context
divided by the maximum sequence count. The previous high-capacity CUDA plan used
16,384 tokens / four slots, and Metal/Vulkan used 8,192 / two: just 4,096 tokens
per request. CPU and the smaller CUDA plans already provided 8,192 per request.

Reference: [llama.cpp context allocation](https://github.com/ggml-org/llama.cpp/blob/6b9ba4f2e8c1436511956f0b3c309e2c9e642071/src/llama-context.cpp#L390).
The starter-context investigation measured an ordinary 100-shelf request at
6,909 text tokens before output; it cannot fit into a 4K slot.

Keep the existing total context allocation and model choices. CUDA now uses two
slots, Metal/Vulkan one, and CPU still one. Each gets 8,192 tokens per request.
This trades some concurrency for room to complete longer automatic tasks without
increasing the configured total KV memory budget. Larger requests still need the
bounded-task recovery; this does not guarantee that every prompt fits.

Verification: five GPU launch cases failed the new capacity check before the
change; five controls passed. Afterward 106 focused checks passed in 5.48 seconds,
covering actual launch argument construction, readiness, provider concurrency,
GPU/CPU fallback, lifecycle, model selection and persona concurrency. Strict
Pyright on hardware.py reported zero errors; `git diff --check` passed.

The process/network boundary was mocked. No GPU model was loaded and no throughput
claim is made. The setting applies when TwinStore starts a managed server after
updating; an already running server needs to be stopped and started. Independently
started llama.cpp servers retain their own configuration.
