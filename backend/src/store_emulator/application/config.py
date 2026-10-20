import logging
import os

from dotenv import load_dotenv

from store_emulator.domain.config import LLMConfig, SimulationConfig

load_dotenv()

logger = logging.getLogger(__name__)

# Environment overrides, so switching provider / running a local OpenAI-compatible
# server / pinning seeds needs no code edit. Values are validated by the Pydantic models.
_LLM_ENV: dict[str, str] = {
    "PARASTORE_LLM_MODEL": "model",
    "PARASTORE_LLM_API_BASE": "api_base",
    "PARASTORE_LLM_TEMPERATURE": "temperature",
    "PARASTORE_LLM_MAX_TOKENS": "max_tokens",
    "PARASTORE_LLM_SEED": "seed",
    "PARASTORE_LLM_TIMEOUT_SEC": "timeout_sec",
    "PARASTORE_LLM_CACHE_DIR": "cache_dir",
}
_SIM_ENV: dict[str, str] = {
    "PARASTORE_ENGINE": "engine_type",
    "PARASTORE_SEED": "seed",
    "PARASTORE_CURRENCY": "currency",
    "PARASTORE_EXPOSURE_MODEL": "exposure_model",
    "PARASTORE_ROUTE_ORDERING": "route_ordering",
    "PARASTORE_BUDGET_TOLERANCE": "budget_tolerance",
}


def local_config() -> SimulationConfig:
    llm: dict[str, object] = {"model": "gemini/gemini-3.1-pro-preview"}
    for env, field in _LLM_ENV.items():
        if os.getenv(env):
            llm[field] = os.environ[env]
    sim: dict[str, object] = {"llm": LLMConfig.model_validate(llm)}
    for env, field in _SIM_ENV.items():
        if os.getenv(env):
            sim[field] = os.environ[env]
    if os.getenv("PARASTORE_BUDGET_TOLERANCE", "").lower() in ("none", "off"):
        sim["budget_tolerance"] = None
    config = SimulationConfig.model_validate(sim)
    overridden = [e for e in (*_LLM_ENV, *_SIM_ENV) if os.getenv(e)]
    if overridden:
        logger.info(f"[config] environment overrides applied: {', '.join(overridden)}")
    return config
