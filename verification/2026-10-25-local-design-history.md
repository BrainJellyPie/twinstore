# Long design conversations on the CPU model

Two separate failures prevented an otherwise valid design request:

- After twenty replies the frontend sent 41 messages. The API permits at most 40,
  so every subsequent request failed until the owner started a new conversation.
  A component-level reproduction reached this exact 21st-request failure.
- A valid 39-message conversation with long Korean text sent 19,103 tokens to the
  real Qwen3.5-0.8B CPU server's 8,192-token context. Both attempted calls received
  HTTP 400 `exceed_context_size_error`; retrying the same input could not recover.

The frontend now sends the latest nineteen complete exchanges plus the new request
(39 messages). The visible conversation and undo history remain intact. The engine
keeps a contiguous recent history within 4,000 UTF-8 bytes, avoids starting with an
orphaned designer reply, and explicitly notes when older messages were omitted.
The complete newest request is always retained, even if it alone exceeds that budget.
The current draft is described separately on every call, so omitting old chat does
not revert its settings. Short conversations produce the same prompts as before.

This is a conservative history allowance for small local contexts, not a tokenizer
or a guarantee for every possible server context size. An older detail outside the
retained conversation may need clarification; it remains visible to the owner.

## Real inference

Same CPU-only Qwen3.5-0.8B Q4_K_M / llama.cpp b11878 configuration as the preceding
design probe: five threads, one slot, thinking off, JSON Schema, temperature 0.2,
seed 0, 900 output tokens. No paid provider or mocked response was used.

The same 39-message, 45,607-character input after the correction used 648 prompt
tokens, completed in one call (4.33 s), and changed only `theme_color` to `#00AA33`.
Raw before/after evidence is under
`/workspace/scratch/cpu-vlm-probe/design-history-{baseline,bounded}/`.

The committed harness also exercised the long history with its standard shop
fixture: one call, 646 prompt tokens, 3.37 s, only the requested colour changed.
It retains both the raw response and before/after option values:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case design-long-history
```

## Actual screenshot exploration

The same VLM also ran production `ModelPolicy` and `run_session` with real shop
screenshots, shuffled control numbers and the standard 240-token decision budget.
Input images and raw replies were saved, and the desktop home screenshot was
visually inspected. These were exploratory visits, not assertions that a shopper
must purchase.

- Desktop: searched for the target shirt, then left. Two vision decisions plus
  the exit survey completed in 25.45 s; no parser/validation fallback occurred.
- Mobile with a welcome popup: eight decisions included closing the popup,
  opening products, adding to the cart and searching. With the exit survey this
  used nine calls in 83.89 s, again with no fallback. The shopper did not consistently
  follow the single-item goal and ended with an abandoned cart at the step cap.

Artifacts: `/workspace/scratch/cpu-vlm-probe/shop-desktop-purchase/` and
`shop-mobile-popup/`; exploratory runner: `shop_probe.py` in their parent directory.
The tiny model's shopping behavior is not validated as realistic by these checks.

## Focused checks

- 30 backend tests passed in 6.04 s, including long ASCII, Korean and emoji history,
  preservation of the current draft and complete latest request, and sparse-update
  SDK validation/cache coverage. Existing LiteLLM logging cleanup warnings remain.
- All 37 designer tests passed in 11.45 s, including sending the 21st request while
  retaining the first visible exchange and keeping the request under the API limit.
- Strict backend type check: zero errors/warnings; backend boot passed. Frontend
  TypeScript and changed-file lint passed. Production build passed in 18.54 s with
  the existing chunk-size and Babel plugin timing warnings.
