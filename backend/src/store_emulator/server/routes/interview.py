"""A shopper's journey through a finished run, and a conversation with that shopper afterwards."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from store_emulator.application import interview as service
from store_emulator.application.errors import AppError
from store_emulator.domain.interview import Interview, InterviewQuestion, Journey

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


@router.get("/{pid}/runs/{run_id}/shoppers/{persona_id}/interview", summary="Interview transcript", response_model=Interview)
def get_interview(pid: str, run_id: str, persona_id: str) -> Interview:
    return _call(lambda: service.get_interview(pid, run_id, persona_id))


@router.post("/{pid}/runs/{run_id}/shoppers/{persona_id}/interview", summary="Ask the shopper a question",
             response_model=Interview)
async def ask(pid: str, run_id: str, persona_id: str, q: InterviewQuestion) -> Interview:
    """The shopper answers in the first person from their persona and this trip only, citing the journey steps the
    answer is about. Returns the whole transcript."""
    return await run_in_threadpool(_call, lambda: service.interview(pid, run_id, persona_id, q, get_config()))


@router.delete("/{pid}/runs/{run_id}/shoppers/{persona_id}/interview", summary="Start the interview over", status_code=204)
def clear(pid: str, run_id: str, persona_id: str) -> None:
    _call(lambda: service.clear_interview(pid, run_id, persona_id))
