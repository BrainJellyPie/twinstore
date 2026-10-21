"""Shopper journeys and interviews for a finished run.

Transcripts live next to the run: `.data/<pid>/runs/<run_id>/interviews/<persona_id>.json`, group
interviews in `.../group_interviews/<group_id>.json`.
"""

import asyncio
import logging
import random
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import cast

from filelock import FileLock, Timeout

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.interview import (
    GroupAnswer,
    GroupInterview,
    GroupInterviewRequest,
    Interview,
    InterviewMessage,
    InterviewQuestion,
    Journey,
    Theme,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face
from store_emulator.engine.interview import ask_shopper, build_journey, code_themes
from store_emulator.engine.perception.shelf_render import render_face

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


@lru_cache(maxsize=64)
def _face_png(base: str, mtime: float, rack_id: str, face: str) -> bytes:
    _, _, store, currency = _run_data(base, mtime)
    rack = next((r for r in store.racks if r.id == rack_id), None)
    if rack is None:
        raise AppError(f"rack not in this run: {rack_id}", 404)
    return render_face(rack, Face(face), currency=currency, width=640, number_on_tag=False).png


def shelf_face_png(pid: str, run_id: str, rack_id: str, face: str) -> bytes:
    """The shelf face as the shoppers of this run saw it (the vision shoppers' renderer, without badges)."""
    _check_id(rack_id, "rack id")
    if face not in ("N", "S", "E", "W"):
        raise AppError(f"invalid face: {face}", 400)
    base = _run_dir(pid, run_id)
    return _face_png(str(base), (base / "output" / "timeline.json").stat().st_mtime, rack_id, face)


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


@contextmanager
def _interview_lock(pid: str, run_id: str, persona_id: str) -> Iterator[None]:
    path = _transcript_path(pid, run_id, persona_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(path.with_suffix(".lock"), timeout=0)
    try:
        lock.acquire()
    except Timeout as e:
        raise AppError("This shopper is answering a question. Try again when the answer is complete.", 409) from e
    try:
        yield
    finally:
        lock.release()


def clear_interview(pid: str, run_id: str, persona_id: str) -> None:
    with _interview_lock(pid, run_id, persona_id):
        _transcript_path(pid, run_id, persona_id).unlink(missing_ok=True)


def interview(pid: str, run_id: str, persona_id: str, q: InterviewQuestion, config: SimulationConfig) -> Interview:
    with _interview_lock(pid, run_id, persona_id):
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


# ── group interviews ────────────────────────────────────────────────────────────

def _segment(customers: dict[str, CustomerResult], req: GroupInterviewRequest) -> list[str]:
    if req.persona_ids:
        missing = [p for p in req.persona_ids if p not in customers]
        if missing:
            raise AppError(f"shoppers not in this run: {', '.join(missing[:5])}", 404)
        return list(dict.fromkeys(req.persona_ids))
    buys = {k: [e for e in c.timeline if e.action == Action.BUY] for k, c in customers.items()}
    browsed = {k for k, c in customers.items() if any(e.action == Action.BROWSE for e in c.timeline)}
    match req.segment:
        case "empty_handed":
            pool = [k for k in customers if not buys[k] and k in browsed]
        case "buyers":
            pool = [k for k in customers if buys[k]]
        case "impulse":
            pool = [k for k in customers if any(e.origin == "impulse" for e in buys[k])]
        case "top_spenders":
            return sorted(customers, key=lambda k: -customers[k].total_spent)[: req.size]
        case "all":
            pool = list(customers)
    if not pool:
        raise AppError(f"no shopper in this run matches '{req.segment}'", 400)
    pool.sort()
    return random.Random(req.seed).sample(pool, min(req.size, len(pool)))


def _groups_dir(pid: str, run_id: str) -> Path:
    return _run_dir(pid, run_id) / "group_interviews"


def group_interview(pid: str, run_id: str, req: GroupInterviewRequest, config: SimulationConfig) -> GroupInterview:
    """The same question to every selected shopper (each answers from their own trip), then themes."""
    customers, personas, store, currency = _load(pid, run_id)
    ids = [i for i in _segment(customers, req) if i in personas]
    journeys = [build_journey(run_id, customers[i], personas[i], store, currency) for i in ids]
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.7, "max_tokens": 700})
    try:
        llm = build_client(llm_config, None, model_ref=req.model.strip() or None)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    question = req.question.strip()

    async def run() -> tuple[list[GroupAnswer], list[str], list[int]]:
        sem = asyncio.Semaphore(6)

        async def one(j: Journey) -> GroupAnswer:
            p = j.persona
            base = GroupAnswer(persona_id=p.id, identity=p.identity, age_group=str(p.age_group), gender=str(p.gender),
                               spent=j.total_spent, units=j.units)
            async with sem:
                try:
                    reply = await ask_shopper(llm, j, store, [], question)
                except Exception as e:  # one shopper failing must not sink the group
                    return base.model_copy(update={"error": f"{type(e).__name__}: {str(e)[:160]}"})
            return base.model_copy(update={"answer": reply.answer, "steps": reply.steps})

        answers = list(await asyncio.gather(*(one(j) for j in journeys)))
        ok = [a for a in answers if a.answer]
        if len(ok) < 2:
            return answers, [], []
        try:
            themes, coded = await code_themes(llm, question, [a.answer for a in ok])
        except Exception as e:  # answers are still worth showing without themes
            logger.warning(f"[interview] theme coding failed: {type(e).__name__}: {e}")
            return answers, [], []
        return answers, themes, coded

    answers, labels, coded = asyncio.run(run())
    ok = [a for a in answers if a.answer]
    if not ok:
        raise AppError(f"no shopper could answer: {answers[0].error if answers else 'nobody selected'}", 502)
    for a, k in zip(ok, coded):
        a.theme = k
    themes = [Theme(label=t, count=sum(1 for k in coded if k == i), share=round(sum(1 for k in coded if k == i) / len(ok), 4))
              for i, t in enumerate(labels)]
    group = GroupInterview(
        group_id=f"grp_{uuid.uuid4().hex[:6]}", run_id=run_id, question=question, segment=req.segment if not req.persona_ids else "all",
        model=req.model.strip() or llm_config.model, created_at=now_iso(), answers=answers, themes=themes,
        errors=sum(1 for a in answers if a.error),
    )
    folder = _groups_dir(pid, run_id)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / f"{group.group_id}.json", group.model_dump(mode="json"))
    return group


def list_group_interviews(pid: str, run_id: str) -> list[GroupInterview]:
    folder = _groups_dir(pid, run_id)
    groups = [GroupInterview.model_validate(read_json(p)) for p in folder.glob("grp_*.json")] if folder.exists() else []
    return sorted(groups, key=lambda g: g.created_at, reverse=True)


def delete_group_interview(pid: str, run_id: str, group_id: str) -> None:
    _check_id(group_id, "group id")
    path = _groups_dir(pid, run_id) / f"{group_id}.json"
    if not path.exists():
        raise AppError(f"group interview not found: {group_id}", 404)
    path.unlink()
