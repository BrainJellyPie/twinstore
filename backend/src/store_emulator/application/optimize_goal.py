"""An optimization's settings read from the goal the manager writes (assistive; nothing starts)."""

import asyncio
import logging

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.engine.optimize.goal import OptimizeGoal, read_goal

from .errors import AppError, model_failure
from .providers import assistive_client
from .scenarios import _store_for  # pyright: ignore[reportPrivateUsage]

logger = logging.getLogger(__name__)


class GoalRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=5, max_length=600, description='e.g. "more impulse sales, keep the fridges, at most 5 changes"')
    model: str = Field(default="", description='model reference; "" = the app text model')


def read(pid: str, sid: str, req: GoalRequest, config: SimulationConfig) -> OptimizeGoal:
    store = _store_for(pid, sid)
    if store is None:
        raise AppError("this layout has no store yet", 400)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 600})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(read_goal(llm, req.text, store))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[optimize] goal reading failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The goal could not be read"), 502) from e
