"""Tests suggested from what a run's shoppers said (a group interview) or what its analyst answered; nothing runs."""

import asyncio
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.interview import GroupInterview
from store_emulator.domain.store import Store
from store_emulator.engine.hypotheses import (
    Hypothesis,
    analyst_text,
    group_text,
    suggest_tests,
)

from .errors import AppError, model_failure
from .interview import (
    _check_id,  # pyright: ignore[reportPrivateUsage]
    _groups_dir,  # pyright: ignore[reportPrivateUsage]
    _load,  # pyright: ignore[reportPrivateUsage]
)
from .providers import assistive_client
from .run_analyst import get_thread
from .storage.io import read_json

logger = logging.getLogger(__name__)


class HypothesisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: Literal["group", "analyst"]
    group_id: str = Field(default="", description="the group interview, when source is group")
    model: str = Field(default="", description='model reference; "" = the app text model')


def suggest(pid: str, run_id: str, req: HypothesisRequest, config: SimulationConfig) -> list[Hypothesis]:
    _, _, store, _ = _load(pid, run_id)
    if req.source == "group":
        _check_id(req.group_id, "group id")
        path = _groups_dir(pid, run_id) / f"{req.group_id}.json"
        if not path.exists():
            raise AppError(f"group interview not found: {req.group_id}", 404)
        said = group_text(GroupInterview.model_validate(read_json(path)))
    else:
        said = analyst_text(get_thread(pid, run_id).messages)
        if not said:
            raise AppError("Ask the analyst a question first.", 400)
    return _suggest(said, store, req.model, config)


def _suggest(said: str, store: Store, model: str, config: SimulationConfig) -> list[Hypothesis]:
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.3, "max_tokens": 900})
    try:
        llm = assistive_client(model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(suggest_tests(llm, said, store))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[hypotheses] {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "No tests could be suggested"), 502) from e
