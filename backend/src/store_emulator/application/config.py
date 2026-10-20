import logging
import os

from dotenv import load_dotenv

from store_emulator.domain.config import LLMConfig, SimulationConfig, VLMGlanceConfig

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
# Vision-language shopper (engine "vlm_glance"); defaults point at a local llama.cpp server.
_VLM_ENV: dict[str, str] = {
    "PARASTORE_VLM_MODEL": "model",
    "PARASTORE_VLM_API_BASE": "api_base",
    "PARASTORE_VLM_TEMPERATURE": "temperature",
    "PARASTORE_VLM_SEED": "seed",
    "PARASTORE_VLM_TIMEOUT_SEC": "timeout_sec",
    "PARASTORE_VLM_CACHE_DIR": "cache_dir",
    "PARASTORE_VLM_STRUCTURED_OUTPUT": "structured_output",
}
_VLM_ENGINE_ENV: dict[str, str] = {
    "PARASTORE_VLM_MAX_GLANCES": "max_glances",
    "PARASTORE_VLM_GLANCE_POLICY": "glance_policy",
    "PARASTORE_VLM_LOOK_BASE": "look_base",
    "PARASTORE_VLM_IMAGE_WIDTH": "image_width",
    "PARASTORE_VLM_PLAN_POLICY": "plan_policy",
    "PARASTORE_VLM_MAX_PLAN_ITEMS": "max_plan_items",
    "PARASTORE_VLM_ENTRANCE_IMAGE": "entrance_image",
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
    vlm_engine = config.engines.vlm_glance
    vlm_llm = vlm_engine.llm.model_dump()
    vlm_llm.update({field: os.environ[env] for env, field in _VLM_ENV.items() if os.getenv(env)})
    vlm_updates: dict[str, object] = {f: os.environ[e] for e, f in _VLM_ENGINE_ENV.items() if os.getenv(e)}
    vlm_engine = VLMGlanceConfig.model_validate({**vlm_engine.model_dump(), **vlm_updates, "llm": vlm_llm})
    config = config.model_copy(update={"engines": config.engines.model_copy(update={"vlm_glance": vlm_engine})})
    overridden = [e for e in (*_LLM_ENV, *_SIM_ENV, *_VLM_ENV, *_VLM_ENGINE_ENV) if os.getenv(e)]
    if overridden:
        logger.info(f"[config] environment overrides applied: {', '.join(overridden)}")
    return config
