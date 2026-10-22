"""About how long and how much model work will take, for a warning before it starts.

Writing customers and model-based runs can take hours on the small model on this computer, or cost real money with
a provider. Above WARN_MINUTES or WARN_USD the app asks first. Times are measured on a real request where one has
been made; prices come from LiteLLM's model price table (None when the model is not in it).
"""

import ipaddress
import logging
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
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def effective_parallel(local: bool, slots: int | None = None) -> float:
    """How many requests run side by side. A model server on this computer shares its processor between its slots
    (one when unknown), so extra slots add about half a request each; a provider takes CLOUD_PARALLEL at once."""
    if not local:
        return float(CLOUD_PARALLEL)
    return 1.0 + 0.5 * max(0, (slots or 1) - 1)


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """What the tokens cost on `model` by LiteLLM's price table; None when the model is not priced there."""
    if not model:
        return None
    try:
        import litellm

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
