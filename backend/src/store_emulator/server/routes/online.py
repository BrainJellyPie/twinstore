"""Online stores of a project: templates, sites and their variants, browsing as a shopper, and runs of virtual
shoppers with web-analytics results."""

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool

from store_emulator.application import online as online_service
from store_emulator.application.errors import AppError
from store_emulator.application.online import (
    BrowseRequest,
    CopySiteRequest,
    CreateSiteRequest,
    OnlineRunView,
    SessionView,
    SiteSummary,
)
from store_emulator.domain.online import OnlineRunRequest, OnlineRunStatus, OnlineSite, OnlineTemplate, PageView

from ..deps import get_config

router = APIRouter(prefix="/api", tags=["online"])
_PNG_CACHE = {"Cache-Control": "no-store"}


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e


@router.get("/online/templates", summary="Ready-made web shops", response_model=list[OnlineTemplate])
def list_templates() -> list[OnlineTemplate]:
    return online_service.list_templates()


@router.get("/online/templates/{template_id}/preview.png", summary="Home page of a template, as a picture")
async def template_preview(template_id: str, currency: str = "USD") -> Response:
    if not currency.isalpha() or len(currency) != 3:
        raise HTTPException(400, "currency must be a three-letter code")
    png = await run_in_threadpool(_call, lambda: online_service.template_preview(template_id, currency.upper()))
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/projects/{pid}/online/sites", summary="The project's online stores", response_model=list[SiteSummary])
def list_sites(pid: str) -> list[SiteSummary]:
    return _call(lambda: online_service.list_sites(pid))


@router.post("/projects/{pid}/online/sites", summary="Create an online store from a template", response_model=OnlineSite)
def create_site(pid: str, req: CreateSiteRequest) -> OnlineSite:
    """`template_id` "from_store" builds the catalog from a layout's shelves (`setup_id`, default the active one)."""
    return _call(lambda: online_service.create_site(pid, req, get_config()))


@router.get("/projects/{pid}/online/sites/{site_id}", summary="One online store", response_model=OnlineSite)
def get_site(pid: str, site_id: str) -> OnlineSite:
    return _call(lambda: online_service.get_site(pid, site_id))


@router.put("/projects/{pid}/online/sites/{site_id}", summary="Save an edited online store", response_model=OnlineSite)
def put_site(pid: str, site_id: str, site: OnlineSite) -> OnlineSite:
    return _call(lambda: online_service.save_site(pid, site_id, site))


@router.post("/projects/{pid}/online/sites/{site_id}/copy", summary="Make a variant of an online store",
             response_model=OnlineSite)
def copy_site(pid: str, site_id: str, req: CopySiteRequest) -> OnlineSite:
    return _call(lambda: online_service.copy_site(pid, site_id, req))


@router.delete("/projects/{pid}/online/sites/{site_id}", summary="Delete an online store")
def delete_site(pid: str, site_id: str) -> dict[str, str]:
    _call(lambda: online_service.delete_site(pid, site_id))
    return {"status": "deleted"}


@router.get("/projects/{pid}/online/sites/{site_id}/preview.png", summary="Home page of a store, as a picture")
async def site_preview(pid: str, site_id: str, device: Literal["desktop", "mobile"] = "desktop") -> Response:
    png = await run_in_threadpool(_call, lambda: online_service.site_preview(pid, site_id, device))
    return Response(png, media_type="image/png", headers=_PNG_CACHE)


@router.post("/projects/{pid}/online/sites/{site_id}/browse", summary="Browse the store as a shopper",
             response_model=PageView)
async def browse(pid: str, site_id: str, req: BrowseRequest) -> PageView:
    """Use one numbered option of the current page (`state` and `option`, with `query` for the search box) and get
    the next page: its screenshot with numbered badges, the options and their boxes, and the new state. Without
    `option`, the page of `state` (or the landing page of a new visit)."""
    return await run_in_threadpool(_call, lambda: online_service.browse(pid, site_id, req))


@router.post("/projects/{pid}/online/runs", summary="Start a run of virtual online shoppers",
             response_model=OnlineRunStatus)
def start_run(pid: str, req: OnlineRunRequest) -> OnlineRunStatus:
    """Every shopper visits every store in `site_ids` (the first is the control), so variants are compared on the
    same people. Policies: "rule" (instant), "vlm" (a vision model looks at each page) or "text" (a text model reads
    it). Runs in the background; poll `GET /online/runs/{run_id}`."""
    return _call(lambda: online_service.start_run(pid, req, get_config()))


@router.get("/projects/{pid}/online/runs", summary="Online runs", response_model=list[OnlineRunStatus])
def list_runs(pid: str) -> list[OnlineRunStatus]:
    return _call(lambda: online_service.list_runs(pid))


@router.get("/projects/{pid}/online/runs/{run_id}", summary="Progress and result of an online run",
            response_model=OnlineRunView)
def get_run(pid: str, run_id: str) -> OnlineRunView:
    return _call(lambda: online_service.get_run(pid, run_id))


@router.delete("/projects/{pid}/online/runs/{run_id}", summary="Delete a finished online run")
def delete_run(pid: str, run_id: str) -> dict[str, str]:
    _call(lambda: online_service.delete_run(pid, run_id))
    return {"status": "deleted"}


@router.get("/projects/{pid}/online/runs/{run_id}/sessions/{variant}/{shopper_id}",
            summary="One shopper's visit, step by step", response_model=SessionView)
def get_session(pid: str, run_id: str, variant: int, shopper_id: str) -> SessionView:
    return _call(lambda: online_service.get_session(pid, run_id, variant, shopper_id))


@router.get("/projects/{pid}/online/runs/{run_id}/sessions/{variant}/{shopper_id}/steps/{step}.png",
            summary="The page a shopper saw at one step")
async def step_screenshot(pid: str, run_id: str, variant: int, shopper_id: str, step: int) -> Response:
    png = await run_in_threadpool(_call, lambda: online_service.step_screenshot(pid, run_id, variant, shopper_id, step))
    return Response(png, media_type="image/png", headers=_PNG_CACHE)


@router.get("/projects/{pid}/online/runs/{run_id}/clickstream.csv", summary="Every click of the run, as CSV")
def export_clickstream(pid: str, run_id: str) -> PlainTextResponse:
    text = _call(lambda: online_service.export_clickstream(pid, run_id))
    return PlainTextResponse("﻿" + text, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{run_id}-clickstream.csv"'})
