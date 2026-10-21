"""Questions about a finished run, answered from its own numbers; the thread is kept next to the run
(`.data/<pid>/runs/<run_id>/analyst.json`)."""

import asyncio
import logging
from pathlib import Path

from filelock import FileLock, Timeout

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.interview import (
    AnalystMessage,
    AnalystQuestion,
    AnalystThread,
)
from store_emulator.domain.types import stable_seed
from store_emulator.engine.run_analyst import answer_run_question, run_facts

from .errors import AppError, model_failure
from .interview import _load, _run_dir  # pyright: ignore[reportPrivateUsage]
from .providers import assistive_model, build_client
from .storage.io import now_iso, read_json, write_json

logger = logging.getLogger(__name__)


def _path(pid: str, run_id: str) -> Path:
    return _run_dir(pid, run_id) / "analyst.json"


def get_thread(pid: str, run_id: str) -> AnalystThread:
    path = _path(pid, run_id)
    return AnalystThread.model_validate(read_json(path)) if path.exists() else AnalystThread(run_id=run_id)


def clear_thread(pid: str, run_id: str) -> None:
    _path(pid, run_id).unlink(missing_ok=True)


def facts(pid: str, run_id: str) -> str:
    customers, personas, store, currency = _load(pid, run_id)
    return run_facts(list(customers.values()), personas, store, currency)


def ask(pid: str, run_id: str, q: AnalystQuestion, config: SimulationConfig) -> AnalystThread:
    path = _path(pid, run_id)
    lock = FileLock(path.with_suffix(".lock"), timeout=0)
    try:
        lock.acquire()
    except Timeout as e:
        raise AppError("The previous question is still being answered. Try again in a moment.", 409) from e
    try:
        thread = get_thread(pid, run_id)
        llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 900})
        model = assistive_model(q.model, llm_config)
        try:
            llm = build_client(llm_config, None, model_ref=model)
        except ValueError as e:
            raise AppError(str(e), 400) from e
        try:
            answer = asyncio.run(answer_run_question(llm, facts(pid, run_id), q.question, thread.messages,
                                                     seed=stable_seed("analyst", run_id, len(thread.messages))))
        except Exception as e:  # provider errors reach the user as advice
            logger.warning(f"[analyst] {pid}/{run_id}: {type(e).__name__}: {e}")
            raise AppError(model_failure(e, "The question could not be answered"), 502) from e
        now = now_iso()
        thread.model = model
        thread.messages += [
            AnalystMessage(role="user", text=q.question, created_at=now),
            AnalystMessage(role="analyst", text=answer.answer, figures=answer.figures, follow_ups=answer.follow_ups, created_at=now_iso()),
        ]
        write_json(path, thread.model_dump(mode="json"))
        return thread
    finally:
        lock.release()
