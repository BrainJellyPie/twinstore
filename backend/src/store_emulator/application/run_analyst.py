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
from store_emulator.engine.run_analyst import (
    DifferenceReading,
    answer_run_question,
    comparison_text,
    explain_difference,
    run_facts,
    suggest_run_questions,
)

from .errors import AppError, model_failure
from .interview import _load, _run_dir  # pyright: ignore[reportPrivateUsage]
from .providers import answered_by, assistive_client, assistive_model
from .setups import setup_tree_transaction
from .storage.io import now_iso, read_json, write_json

logger = logging.getLogger(__name__)


def _path(pid: str, run_id: str) -> Path:
    return _run_dir(pid, run_id) / "analyst.json"


def get_thread(pid: str, run_id: str) -> AnalystThread:
    path = _path(pid, run_id)
    return AnalystThread.model_validate(read_json(path)) if path.exists() else AnalystThread(run_id=run_id)


def clear_thread(pid: str, run_id: str) -> None:
    path = _path(pid, run_id)
    lock = FileLock(path.with_suffix(".lock"), timeout=0)
    try:
        with setup_tree_transaction(pid):
            _path(pid, run_id)
            with lock:
                path.unlink(missing_ok=True)
    except Timeout as e:
        raise AppError("The previous question is still being answered. Try again in a moment.", 409) from e


def facts(pid: str, run_id: str) -> str:
    customers, personas, store, currency = _load(pid, run_id)
    return run_facts(list(customers.values()), personas, store, currency)


def ask(pid: str, run_id: str, q: AnalystQuestion, config: SimulationConfig) -> AnalystThread:
    path = _path(pid, run_id)
    lock = FileLock(path.with_suffix(".lock"), timeout=0)
    try:
        with setup_tree_transaction(pid):
            _path(pid, run_id)
            try:
                lock.acquire()
            except Timeout as e:
                raise AppError("The previous question is still being answered. Try again in a moment.", 409) from e
            thread = get_thread(pid, run_id)
            sheet = facts(pid, run_id)
        llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 1600})
        model = assistive_model(q.model, llm_config)
        try:
            llm = assistive_client(model, llm_config)
        except ValueError as e:
            raise AppError(str(e), 400) from e
        try:
            answer = asyncio.run(answer_run_question(llm, sheet, q.question, thread.messages,
                                                     seed=stable_seed("analyst", run_id, len(thread.messages))))
        except Exception as e:  # provider errors reach the user as advice
            logger.warning(f"[analyst] {pid}/{run_id}: {type(e).__name__}: {e}")
            raise AppError(model_failure(e, "The question could not be answered"), 502) from e
        now = now_iso()
        thread.model = answered_by(llm, model)
        thread.messages += [
            AnalystMessage(role="user", text=q.question, created_at=now),
            AnalystMessage(role="analyst", text=answer.answer, figures=answer.figures, follow_ups=answer.follow_ups, created_at=now_iso()),
        ]
        with setup_tree_transaction(pid):
            write_json(_path(pid, run_id), thread.model_dump(mode="json"))
        return thread
    finally:
        lock.release()


def suggest(pid: str, run_id: str, model: str, config: SimulationConfig) -> list[str]:
    """Three starter questions read off this run's fact sheet (what stands out); nothing is kept."""
    sheet = facts(pid, run_id)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.3, "max_tokens": 500})
    try:
        llm = assistive_client(model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(suggest_run_questions(llm, sheet))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[analyst] suggestions {pid}/{run_id}: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "No questions could be suggested"), 502) from e


def explain_comparison(pid: str, run_a: str, run_b: str, model: str, config: SimulationConfig) -> DifferenceReading:
    """Why run B differs from run A: the paired comparison plus both runs' fact sheets, read by the text model."""
    from .simulation import (
        compare_project_runs,  # late import: simulation pulls in the engines
    )

    try:
        report = compare_project_runs(pid, run_a, run_b, n_bootstrap=1000)
    except FileNotFoundError as e:
        raise AppError(str(e), 404) from e
    rows = [(m.metric, m.mean_a, m.mean_b, m.diff, m.ci_low, m.ci_high) for m in report.metrics]
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 2500})
    try:
        llm = assistive_client(model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        currency = _load(pid, run_b)[3]
        return asyncio.run(explain_difference(llm, comparison_text(rows, currency), facts(pid, run_a), facts(pid, run_b),
                                              (run_a, run_b)))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[analyst] explain {run_a} vs {run_b}: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The difference could not be explained"), 502) from e
