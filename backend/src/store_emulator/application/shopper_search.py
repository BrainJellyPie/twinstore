"""Shoppers of a finished run found from a sentence: the text model writes the filter, the run's records decide."""

import asyncio
import logging

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.engine.shopper_filter import ShopperMatch, find_shoppers

from .errors import AppError, model_failure
from .interview import _load  # pyright: ignore[reportPrivateUsage]
from .providers import assistive_client

logger = logging.getLogger(__name__)


class ShopperSearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=3, max_length=400, description='e.g. "women in their 20s who left empty-handed"')
    model: str = Field(default="", description='model reference; "" = the app text model')


def find(pid: str, run_id: str, req: ShopperSearchRequest, config: SimulationConfig) -> ShopperMatch:
    customers, personas, store, currency = _load(pid, run_id)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 900})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(find_shoppers(llm, req.text, customers, personas, store, currency))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[shoppers] search failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The shoppers could not be found"), 502) from e
