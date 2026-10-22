"""A neighborhood spec written by the text model from a description of the area (assistive; nothing is generated)."""

import asyncio
import logging

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.engine.town_writer import DescribedTown, describe_town

from .errors import AppError, model_failure
from .providers import assistive_client

logger = logging.getLogger(__name__)


class TownDescribeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=5, max_length=800, description="the area around the store in plain words")
    seed: int = 0
    model: str = Field(default="", description='model reference; "" = the app text model')


def describe(req: TownDescribeRequest, config: SimulationConfig) -> DescribedTown:
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 600})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(describe_town(llm, req.text, req.seed))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[town] describe failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The neighborhood could not be set up"), 502) from e
