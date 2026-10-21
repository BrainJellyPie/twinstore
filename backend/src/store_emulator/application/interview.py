"""Shopper journeys and interviews for a finished run.

Transcripts live next to the run: `.data/<pid>/runs/<run_id>/interviews/<persona_id>.json`.
"""

import asyncio
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import cast

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.interview import Interview, InterviewMessage, InterviewQuestion, Journey
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.interview import ask_shopper, build_journey

from .errors import AppError
from .providers import build_client
from .storage.io import DATA_DIR, now_iso, read_json, write_json

logger = logging.getLogger(__name__)

# Town arrivals append "~t<number>" to persona IDs; path separators remain invalid.
_ID = re.compile(r"[A-Za-z0-9_~-]{1,80}")


def _check_id(value: str, what: str) -> None:
    if not _ID.fullmatch(value):
        raise AppError(f"invalid {what}: {value}", 400)


def _run_dir(pid: str, run_id: str) -> Path:
    _check_id(pid, "project id")
    _check_id(run_id, "run id")
    base = Path(DATA_DIR) / pid / "runs" / run_id
    if not (base / "output" / "timeline.json").exists():
        raise AppError(f"run has no results: {run_id}", 404)
    return base


@lru_cache(maxsize=4)
def _run_data(base: str, mtime: float) -> tuple[dict[str, CustomerResult], dict[str, Persona], Store, str]:
    root = Path(base)
    customers = {c["persona_id"]: CustomerResult.model_validate(c) for c in read_json(root / "output" / "timeline.json")}
    raw_personas = read_json(root / "output" / "personas.json")
    personas = {k: Persona.model_validate(v) for k, v in raw_personas.items()}
    store = Store.model_validate(read_json(root / "input" / "store.json"))
    summary_path = root / "output" / "summary.json"
    summary = cast(dict[str, object], read_json(summary_path)) if summary_path.exists() else {}
    currency = str(summary.get("currency") or "USD")
    return customers, personas, store, "USD" if currency == "USD_CENTS" else currency.upper()


def _load(pid: str, run_id: str) -> tuple[dict[str, CustomerResult], dict[str, Persona], Store, str]:
    base = _run_dir(pid, run_id)
    return _run_data(str(base), (base / "output" / "timeline.json").stat().st_mtime)


def get_journey(pid: str, run_id: str, persona_id: str) -> Journey:
    _check_id(persona_id, "shopper id")
    customers, personas, store, currency = _load(pid, run_id)
    customer = customers.get(persona_id)
    persona = personas.get(persona_id)
    if customer is None or persona is None:
        raise AppError(f"shopper not in this run: {persona_id}", 404)
    return build_journey(run_id, customer, persona, store, currency)


def _transcript_path(pid: str, run_id: str, persona_id: str) -> Path:
    _check_id(persona_id, "shopper id")
    return _run_dir(pid, run_id) / "interviews" / f"{persona_id}.json"


def get_interview(pid: str, run_id: str, persona_id: str) -> Interview:
    path = _transcript_path(pid, run_id, persona_id)
    if not path.exists():
        return Interview(run_id=run_id, persona_id=persona_id)
    return Interview.model_validate(read_json(path))


def clear_interview(pid: str, run_id: str, persona_id: str) -> None:
    _transcript_path(pid, run_id, persona_id).unlink(missing_ok=True)


def interview(pid: str, run_id: str, persona_id: str, q: InterviewQuestion, config: SimulationConfig) -> Interview:
    journey = get_journey(pid, run_id, persona_id)
    _, _, store, _ = _load(pid, run_id)
    transcript = get_interview(pid, run_id, persona_id)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.7, "max_tokens": 700})
    try:
        llm = build_client(llm_config, None, model_ref=q.model.strip() or None)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        reply = asyncio.run(ask_shopper(llm, journey, store, transcript.messages, q.question.strip()))
    except Exception as e:  # provider errors reach the user as a message, not a 500
        logger.warning(f"[interview] {pid}/{run_id}/{persona_id}: {type(e).__name__}: {e}")
        raise AppError(f"the shopper could not answer ({type(e).__name__}): {str(e)[:200]}", 502) from e
    now = now_iso()
    transcript.model = q.model.strip() or llm_config.model
    transcript.messages += [
        InterviewMessage(role="interviewer", text=q.question.strip(), created_at=now),
        InterviewMessage(role="shopper", text=reply.answer, steps=reply.steps, created_at=now_iso()),
    ]
    path = _transcript_path(pid, run_id, persona_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, transcript.model_dump(mode="json"))
    return transcript
