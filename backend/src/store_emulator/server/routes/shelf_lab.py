"""Shelf Lab: counterfactual edits, sim2real panels and compliance audits on a shelf capture."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from store_emulator.application import shelf_lab as lab
from store_emulator.application.restock_order import export_order, preview_order
from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import (
    AuditRequest,
    LabJobView,
    PackageAsset,
    PackageUpdate,
    RivalReport,
    RivalRequest,
    Sim2RealRequest,
)
from store_emulator.domain.shelf_lab import EditedShelf, LabJobStatus, PhotoEdit
from store_emulator.domain.restock_order import RestockOrderPlan, RestockOrderRequest

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["shelf lab"])


class EditRequest(BaseModel):
    edits: list[PhotoEdit] = Field(min_length=1, max_length=40, description="applied in order")


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/{pid}/lab/packages", summary="Upload a product image", response_model=PackageAsset)
async def upload_package(
    pid: str,
    image: Annotated[UploadFile, File(description="PNG with transparency, or any photo on a plain background")],
    name: Annotated[str, Form()] = "",
    brand: Annotated[str, Form()] = "",
    sku: Annotated[str, Form(description="the store product this image shows")] = "",
    remove_background: Annotated[bool, Form()] = True,
) -> PackageAsset:
    """Product images serve Shelf Lab's "new package" edits, packaging A/B tests and survey stimuli."""
    data = await image.read()
    return await run_in_threadpool(_call, lambda: lab.upload_package(
        pid, data, image.filename or "package", name=name, brand=brand, sku=sku, remove_background=remove_background,
    ))


class PackageReadRequest(BaseModel):
    setup_id: str = Field(default="", description="a layout whose products the pack may be linked to")
    model: str = Field(default="", description='vision model reference; "" = the app vision model (or a cloud one when it is off)')


@router.post("/{pid}/lab/packages/{aid}/read", summary="Read a product image with a vision model", response_model=lab.PackageRead)
async def read_package(pid: str, aid: str, req: PackageReadRequest) -> lab.PackageRead:
    """Name, brand and size as printed on the pack replace the file-name guess; an exact product of the layout is
    linked when the image is not linked yet."""
    return await run_in_threadpool(_call, lambda: lab.read_package(pid, aid, setup_id=req.setup_id, model=req.model, config=get_config()))


@router.patch("/{pid}/lab/packages/{aid}", summary="Rename or link a product image", response_model=PackageAsset)
def update_package(pid: str, aid: str, upd: PackageUpdate) -> PackageAsset:
    return _call(lambda: lab.update_package(pid, aid, upd))


@router.delete("/{pid}/lab/packages/{aid}", summary="Delete a product image", status_code=204)
def delete_package(pid: str, aid: str) -> None:
    _call(lambda: lab.delete_package(pid, aid))


@router.get("/{pid}/lab/packages", summary="Uploaded package images", response_model=list[PackageAsset])
def list_packages(pid: str) -> list[PackageAsset]:
    return _call(lambda: lab.list_packages(pid))


@router.get("/{pid}/lab/packages/{aid}", summary="A package image")
def package(pid: str, aid: str) -> FileResponse:
    return FileResponse(_call(lambda: lab.package_path(pid, aid)), media_type="image/png")


@router.post("/{pid}/captures/{cid}/edits", summary="Counterfactual edit of the photo", response_model=EditedShelf)
async def create_edit(pid: str, cid: str, req: EditRequest) -> EditedShelf:
    """Swap products, empty a run (stock-out), put a new package on the shelf, change a price tag or hang a
    promotion sign. Returns the changed boxes (exact ground truth) and the planogram the edited photo shows."""
    return await run_in_threadpool(_call, lambda: lab.create_edit(pid, cid, req.edits))


@router.get("/{pid}/captures/{cid}/edits", summary="Edits of a capture", response_model=list[EditedShelf])
def list_edits(pid: str, cid: str) -> list[EditedShelf]:
    return _call(lambda: lab.list_edits(pid, cid))


@router.get("/{pid}/captures/{cid}/edits/{eid}", summary="One edit", response_model=EditedShelf)
def get_edit(pid: str, cid: str, eid: str) -> EditedShelf:
    return _call(lambda: lab.get_edit(pid, cid, eid))


@router.get("/{pid}/captures/{cid}/edits/{eid}/{kind}", summary="Edited photo (image) or ground-truth mask (mask)")
def edit_file(pid: str, cid: str, eid: str, kind: Literal["image", "mask"]) -> FileResponse:
    path = _call(lambda: lab.edit_file(pid, cid, eid, kind))
    return FileResponse(path, media_type="image/jpeg" if kind == "image" else "image/png")


@router.delete("/{pid}/captures/{cid}/edits/{eid}", summary="Delete an edit", status_code=204)
def delete_edit(pid: str, cid: str, eid: str) -> None:
    _call(lambda: lab.delete_edit(pid, cid, eid))


@router.post("/{pid}/captures/{cid}/sim2real", summary="Same shoppers on the photo and its rendered twin", response_model=LabJobStatus)
def start_sim2real(pid: str, cid: str, req: Sim2RealRequest) -> LabJobStatus:
    """Runs in the background; poll `GET .../lab/jobs/{jid}`."""
    return _call(lambda: lab.start_sim2real(pid, cid, req, get_config()))


@router.post("/{pid}/captures/{cid}/audit", summary="Planogram compliance audit with revenue impact", response_model=LabJobStatus)
def start_audit(pid: str, cid: str, req: AuditRequest) -> LabJobStatus:
    """Compares the photo with the layout's reference face and prices the differences by paired simulation."""
    return _call(lambda: lab.start_audit(pid, cid, req, get_config()))


@router.get("/{pid}/captures/{cid}/lab/jobs", summary="Sim2real and audit jobs of a capture", response_model=list[LabJobStatus])
def list_jobs(pid: str, cid: str) -> list[LabJobStatus]:
    return _call(lambda: lab.list_jobs(pid, cid))


@router.get("/{pid}/captures/{cid}/lab/jobs/{jid}", summary="Job status and report", response_model=LabJobView)
def get_job(pid: str, cid: str, jid: str) -> LabJobView:
    return _call(lambda: lab.get_job(pid, cid, jid))


@router.post("/{pid}/captures/{cid}/lab/jobs/{jid}/restock-order", response_model=RestockOrderPlan, summary="Preview stockroom transfers and budgeted whole-pack purchases")
def restock_order(pid: str, cid: str, jid: str, req: RestockOrderRequest) -> RestockOrderPlan:
    return _call(lambda: preview_order(pid, cid, jid, req))


@router.post("/{pid}/captures/{cid}/lab/jobs/{jid}/restock-order.csv", summary="Export a budgeted restocking worksheet")
def export_restock_order(pid: str, cid: str, jid: str, req: RestockOrderRequest) -> PlainTextResponse:
    text = _call(lambda: export_order(pid, cid, jid, req))
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{jid}-restock-order.csv"'})


@router.post("/{pid}/captures/{cid}/rival", summary="Compare a rival's shelf with ours", response_model=RivalReport)
async def rival(pid: str, cid: str, req: RivalRequest) -> RivalReport:
    """Price index and assortment overlap of a rival's captured shelf against our layout; optionally scales the rival
    venue's pull in the neighborhood by the price-adjusted factor. Products whose names differ from ours are matched
    by the text model (same brand, variant and size only) unless `match_with_model` is false."""
    config = get_config()
    return await run_in_threadpool(_call, lambda: lab.compare_rival_capture(pid, cid, req, default_currency=config.currency, config=config))
