"""Assistive drafts for forms that exist before a project does (nothing is saved)."""

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from store_emulator.application import setup_assist
from store_emulator.application.errors import AppError
from store_emulator.engine.assist_router import AssistRoute

from ..deps import get_config

router = APIRouter(prefix="/api/assist", tags=["assist"])


@router.post("/customer-profile", summary="Draft a customer profile for a new store", response_model=setup_assist.ProfileDraft)
async def customer_profile(req: setup_assist.ProfileRequest) -> setup_assist.ProfileDraft:
    """Three to five sentences on who shops at the store, when and why, from what the form already says."""
    def run() -> setup_assist.ProfileDraft:
        try:
            return setup_assist.customer_profile(req, get_config())
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e

    return await run_in_threadpool(run)


@router.post("/route", summary="Where a plain-words request belongs", response_model=AssistRoute)
async def route(req: setup_assist.RouteRequest) -> AssistRoute:
    """A/B test, conjoint study, staff script, neighborhood, a question about the last run, or none of these."""
    def run() -> AssistRoute:
        try:
            return setup_assist.route(req, get_config())
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e

    return await run_in_threadpool(run)
