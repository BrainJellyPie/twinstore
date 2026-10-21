"""A shopper's journey through a finished run, and a conversation with that shopper afterwards."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Response
from starlette.concurrency import run_in_threadpool

from store_emulator.application import interview as service
from store_emulator.application.errors import AppError
from store_emulator.domain.interview import (
    GroupInterview,
    GroupInterviewRequest,
    Interview,
    InterviewQuestion,
    Journey,
    SuggestionRequest,
)

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["shopper interviews"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/{pid}/runs/{run_id}/shoppers/{persona_id}/journey", summary="One shopper's trip, step by step",
            response_model=Journey)
async def journey(pid: str, run_id: str, persona_id: str) -> Journey:
    """Every stop with its wall-clock time, shelf, product and the thought recorded at that step, the walked path,
    and the products on each shelf face the shopper stopped at."""
    return await run_in_threadpool(_call, lambda: service.get_journey(pid, run_id, persona_id))


@router.get("/{pid}/runs/{run_id}/racks/{rack_id}/faces/{face}.png", summary="A shelf face as the run's shoppers saw it",
            response_class=Response)
async def shelf_face(pid: str, run_id: str, rack_id: str, face: str) -> Response:
    png = await run_in_threadpool(_call, lambda: service.shelf_face_png(pid, run_id, rack_id, face))
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{pid}/runs/{run_id}/shoppers/{persona_id}/interview", summary="Interview transcript", response_model=Interview)
def get_interview(pid: str, run_id: str, persona_id: str) -> Interview:
    return _call(lambda: service.get_interview(pid, run_id, persona_id))


@router.post("/{pid}/runs/{run_id}/shoppers/{persona_id}/interview", summary="Ask the shopper a question",
             response_model=Interview)
async def ask(pid: str, run_id: str, persona_id: str, q: InterviewQuestion) -> Interview:
    """The shopper answers in the first person from their persona and this trip only, citing the journey steps the
    answer is about. Returns the whole transcript."""
    return await run_in_threadpool(_call, lambda: service.interview(pid, run_id, persona_id, q, get_config()))


@router.post("/{pid}/runs/{run_id}/shoppers/{persona_id}/interview/suggestions", summary="Suggest next questions",
             response_model=Interview)
async def suggest(pid: str, run_id: str, persona_id: str, req: SuggestionRequest) -> Interview:
    """Up to three questions a researcher would ask next, written by the model for this trip and the conversation so
    far. Kept with the transcript (`suggestions`, `suggested_after`) until the conversation moves on."""
    return await run_in_threadpool(_call, lambda: service.suggest_questions(pid, run_id, persona_id, req, get_config()))


@router.delete("/{pid}/runs/{run_id}/shoppers/{persona_id}/interview", summary="Start the interview over", status_code=204)
def clear(pid: str, run_id: str, persona_id: str) -> None:
    _call(lambda: service.clear_interview(pid, run_id, persona_id))


@router.post("/{pid}/runs/{run_id}/group-interviews", summary="Ask many shoppers the same question", response_model=GroupInterview)
async def group_interview(pid: str, run_id: str, req: GroupInterviewRequest) -> GroupInterview:
    """Shoppers of a segment (all, empty-handed, buyers, impulse buyers, top spenders) or the given ids each answer from
    their own trip; the answers are then coded into themes (counts come from per-answer assignments)."""
    return await run_in_threadpool(_call, lambda: service.group_interview(pid, run_id, req, get_config()))


@router.get("/{pid}/runs/{run_id}/group-interviews", summary="Group interviews of a run", response_model=list[GroupInterview])
def list_group_interviews(pid: str, run_id: str) -> list[GroupInterview]:
    return _call(lambda: service.list_group_interviews(pid, run_id))


@router.delete("/{pid}/runs/{run_id}/group-interviews/{group_id}", summary="Delete a group interview", status_code=204)
def delete_group_interview(pid: str, run_id: str, group_id: str) -> None:
    _call(lambda: service.delete_group_interview(pid, run_id, group_id))
