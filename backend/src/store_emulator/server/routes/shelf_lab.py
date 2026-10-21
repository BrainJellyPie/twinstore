"""Shelf Lab: counterfactual edits, sim2real panels and compliance audits on a shelf capture."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from store_emulator.application import shelf_lab as lab
from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import AuditRequest, LabJobView, PackageAsset, Sim2RealRequest
from store_emulator.domain.shelf_lab import EditedShelf, LabJobStatus, PhotoEdit

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["shelf lab"])


class EditRequest(BaseModel):
    edits: list[PhotoEdit] = Field(min_length=1, max_length=40, description="applied in order")


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/{pid}/lab/packages", summary="Upload a package image for replace edits", response_model=PackageAsset)
async def upload_package(pid: str, image: Annotated[UploadFile, File(description="PNG with transparency, or any photo on a plain background")]) -> PackageAsset:
    data = await image.read()
    return await run_in_threadpool(_call, lambda: lab.upload_package(pid, data, image.filename or "package"))


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
