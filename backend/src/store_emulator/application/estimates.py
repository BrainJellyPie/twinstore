"""About how long and how much model work will take, for a warning before it starts.

Writing customers and model-based runs can take hours on the small model on this computer, or cost real money with
a provider. Above WARN_MINUTES or WARN_USD the app asks first. Times are measured on a real request where one has
been made; prices come from LiteLLM's model price table (None when the model is not in it).
"""

import ipaddress
import logging
from typing import cast
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

WARN_MINUTES = 10.0
WARN_USD = 1.0
# Requests a provider is sent at once (the persona writer's and the simulator's limits).
CLOUD_PARALLEL = 20


def is_local_base(api_base: str | None) -> bool:
    """A model server on this computer (llama.cpp, vLLM, Ollama on a loopback address): free to call."""
    if not api_base:
        return False
    host = urlparse(api_base if "://" in api_base else f"http://{api_base}").hostname or ""
    if host in {"localhost", "localhost."}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def effective_parallel(local: bool, slots: int | None = None) -> float:
    """How many requests run side by side. A model server on this computer shares its processor between its slots
    (one when unknown), so extra slots add about half a request each. Provider work respects both the writer's
    CLOUD_PARALLEL cap and any lower limit configured for the client."""
    if not local:
        return float(min(CLOUD_PARALLEL, max(1, slots if slots is not None else CLOUD_PARALLEL)))
    return 1.0 + 0.5 * max(0, (slots or 1) - 1)


# LiteLLM's prices (USD per input and output token) for the preset models its bundled table lacks, as its online table
# listed them on 2026-10-23. LiteLLM downloads that table when the app starts; offline, or when the download fails, it
# falls back to the bundled one, and the default models would have no price: no cost in the warning before a run.
# A price the download brought always wins over these.
_PRESET_PRICES: dict[str, tuple[float, float, str]] = {
    "gpt-6-luna": (1e-07, 5e-07, "openai"),
    "gpt-6-sol": (2e-06, 1e-05, "openai"),
    "gpt-5.6-luna": (2e-07, 1.2e-06, "openai"),
    "claude-haiku-5-5": (1e-07, 5e-07, "anthropic"),
    "claude-sonnet-5-5": (2e-06, 1e-05, "anthropic"),
    "claude-opus-5-5": (4e-06, 2e-05, "anthropic"),
    "gemini/gemini-3.8-flash": (7.5e-07, 3.75e-06, "gemini"),
    "gemini/gemini-3.5-flash-lite": (3e-07, 2.5e-06, "gemini"),
    "gemini/gemini-4-argon": (2e-06, 1e-05, "gemini"),
}


def _ensure_preset_prices() -> None:
    import litellm

    priced = cast(dict[str, object], getattr(litellm, "model_cost", {}))
    missing = {name: {"input_cost_per_token": prompt, "output_cost_per_token": completion,
                      "litellm_provider": provider, "mode": "chat"}
               for name, (prompt, completion, provider) in _PRESET_PRICES.items() if name not in priced}
    if missing:
        litellm.register_model(missing)


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """What the tokens cost on `model` by LiteLLM's price table; None when the model is not priced there."""
    if not model:
        return None
    try:
        import litellm

        _ensure_preset_prices()

        prompt, completion = litellm.cost_per_token(
            model=model, prompt_tokens=max(0, prompt_tokens), completion_tokens=max(0, completion_tokens),
        )
    except Exception:  # an unknown model raises; a price is a nicety, never a reason to fail
        logger.debug("no price for %s", model, exc_info=True)
        return None
    total = float(prompt) + float(completion)
    return total if total > 0 else None


def should_warn(minutes: float, cost: float | None) -> bool:
    return minutes >= WARN_MINUTES or (cost is not None and cost >= WARN_USD)
