"""A model's reading of a finished concept, shelf, conjoint or staff-script study.

Kept next to the study as `reading.json`, shown with the results and added (labelled) to the print-ready report.
"""

import asyncio
import logging
from typing import Literal

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.engine.marketing.reading import (
    Reason,
    StudyReading,
    compact_report,
    read_study,
)

from .errors import AppError, model_failure
from .marketing import (
    _job_dir,  # pyright: ignore[reportPrivateUsage]
    _status,  # pyright: ignore[reportPrivateUsage]
    get_conjoint,
    get_shelf_test,
    get_survey,
    load_reading,
)
from .providers import build_client
from .staff_pitch import get_pitch
from .storage.io import now_iso, write_json

logger = logging.getLogger(__name__)

StudyKind = Literal["survey", "shelf", "conjoint", "pitch"]

_STUDY: dict[StudyKind, str] = {
    "survey": "concept test (each respondent rated the products shown and said why)",
    "shelf": "virtual shelf test (the same respondents saw the control shelf and the test shelf)",
    "conjoint": "choice-based conjoint study",
    "pitch": "paired staff sales-script test (each respondent heard script A and script B)",
}
_EMPTY: dict[StudyKind, str] = {
    "survey": "the concept test has no answers yet", "shelf": "the shelf test has no results yet",
    "conjoint": "the conjoint study has no answers yet", "pitch": "this staff script test has no report yet",
}


def _material(pid: str, kind: StudyKind, jid: str) -> tuple[str, str, list[Reason]]:
    """The study's report as compact JSON, the open question, and the open answers (with their arm)."""
    match kind:
        case "survey":
            survey = get_survey(pid, jid).report
            if survey is None:
                raise AppError(_EMPTY[kind], 409)
            return (compact_report(survey, {"answers"}), "In one sentence: why did you answer that way?",
                    [Reason(text=a.why) for a in survey.answers if a.why and not a.error])
        case "shelf":
            shelf = get_shelf_test(pid, jid).report
            if shelf is None:
                raise AppError(_EMPTY[kind], 409)
            return (compact_report(shelf, {"choices"}), "Why did you take that product (or nothing) from the shelf?",
                    [Reason(text=c.why, group=c.arm) for c in shelf.choices if c.why and not c.error])
        case "conjoint":
            conjoint = get_conjoint(pid, jid).report
            if conjoint is None:
                raise AppError(_EMPTY[kind], 409)
            return (compact_report(conjoint, {"answers"}), "In one sentence, what mattered most in your choices?",
                    [Reason(text=a.why) for a in conjoint.answers if a.why and not a.error])
        case "pitch":
            pitch = get_pitch(pid, jid).report
            if pitch is None:
                raise AppError(_EMPTY[kind], 409)
            reasons = [Reason(text=rating.reason, group=arm)
                       for a in pitch.answers for arm, rating in (("A", a.a), ("B", a.b)) if rating is not None]
            return compact_report(pitch, {"answers"}), "Why did you rate the script that way?", reasons


def get_reading(pid: str, kind: StudyKind, jid: str) -> StudyReading | None:
    _status(pid, kind, jid)  # 404 for a study that does not exist
    return load_reading(pid, kind, jid)


def write_reading(pid: str, kind: StudyKind, jid: str, model: str, config: SimulationConfig) -> StudyReading:
    """Code the open answers into themes and write a commentary on the numbers; replaces an earlier reading."""
    report_json, question, reasons = _material(pid, kind, jid)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.3, "max_tokens": 2000})
    try:
        llm = build_client(llm_config, None, model_ref=model.strip() or None)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        reading = asyncio.run(read_study(llm, _STUDY[kind], report_json, question, reasons))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[reading] {kind} {jid}: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The reading could not be written"), 502) from e
    reading = reading.model_copy(update={"model": model.strip() or llm_config.model, "created_at": now_iso()})
    write_json(_job_dir(pid, kind, jid) / "reading.json", reading.model_dump(mode="json"))
    return reading


def delete_reading(pid: str, kind: StudyKind, jid: str) -> None:
    (_job_dir(pid, kind, jid) / "reading.json").unlink(missing_ok=True)
