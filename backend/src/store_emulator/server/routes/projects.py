import json
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, field_validator

from store_emulator.application import projects as project_service
from store_emulator.application.errors import AppError
from store_emulator.domain.persona import Persona
from store_emulator.server.schemas import (
    CreateStoreRequest,
    CreateStoreResponse,
    StatusResponse,
)
from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["projects"])


class UpdateMetadataRequest(BaseModel):
    """Project metadata update request."""
    name: str | None = None
    description: str | None = None
    address: str | None = None
    customer_profile: str | None = None


class SavePersonasRequest(BaseModel):
    """Persona save request."""
    personas: list[Persona]

    @field_validator("personas")
    @classmethod
    def validate_identifiers(cls, personas: list[Persona]) -> list[Persona]:
        ids = [persona.id for persona in personas]
        if any(not identifier.strip() for identifier in ids):
            raise ValueError("Persona IDs must not be blank.")
        if len(ids) != len(set(ids)):
            raise ValueError("Persona IDs must be unique.")
        return personas


@router.get("", summary="List projects")
async def list_projects() -> list[dict[str, Any]]:
    """List metadata for all projects. Each item carries a `status` badge.

    **status values:**
    - `"Setting up"` — store or personas incomplete
    - `"Ready"` — store + personas present, not yet simulated
    - `"Simulated"` — at least one completed simulation run exists"""
    return project_service.list_projects()


@router.get("/{pid}", summary="Get project")
async def get_project(pid: str) -> dict[str, Any]:
    """Load the full project.

    **Returns:**
    - `projectId`, `metadata` — project info
    - `personas` — project-wide persona array
    - `state` — `{ activeSetupId }`
    - `setups` — setup summaries (store excluded)
    - `personasLocked` — true if simulation history exists (personas read-only)"""
    try:
        return project_service.load_project(pid)
    except FileNotFoundError:
        raise HTTPException(404, "project not found")


@router.put("/{pid}/metadata", summary="Update metadata", response_model=StatusResponse)
async def update_metadata(pid: str, req: UpdateMetadataRequest) -> StatusResponse:
    """Update project metadata (name, description, address, customer_profile)."""
    try:
        project_service.update_project_metadata(
            pid,
            name=req.name,
            description=req.description,
            address=req.address,
            customer_profile=req.customer_profile,
        )
    except FileNotFoundError:
        raise HTTPException(404, "project not found")
    return StatusResponse(status="saved")


@router.put("/{pid}/personas", summary="Save personas", response_model=StatusResponse)
async def save_personas(pid: str, req: SavePersonasRequest) -> StatusResponse:
    """Save project personas. **Returns 409 during generation/simulation or if simulation history exists.**"""
    try:
        project_service.save_project_personas(pid, personas=[p.model_dump(mode="json") for p in req.personas])
    except FileNotFoundError:
        raise HTTPException(404, "project not found")
    except AppError as e:
        raise HTTPException(409, str(e))
    return StatusResponse(status="saved")


@router.delete("/{pid}", summary="Delete project", response_model=StatusResponse)
async def delete_project(pid: str) -> StatusResponse:
    """Permanently delete the project and child data. Returns 409 while a background job is active."""
    try:
        project_service.delete_project(pid)
    except FileNotFoundError:
        raise HTTPException(404, "project not found")
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e
    return StatusResponse(status="deleted")


SUPPLEMENTAL_MAX_BYTES = 10 * 1024 * 1024
SUPPLEMENTAL_ALLOWED_EXTS = {".csv", ".xlsx"}


@router.post("/create-store", summary="Create project from wizard (no image)", response_model=CreateStoreResponse)
async def create_store(
    meta: str = Form(..., description="JSON-encoded CreateStoreRequest"),
    supplemental: UploadFile | None = File(None, description="Optional supplemental data (csv/xlsx, ≤10MB)"),
) -> dict[str, Any]:
    """Wizard endpoint. No image; persona generation kicks off after empty-setup creation."""
    try:
        meta_dict = json.loads(meta)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, f"meta JSON parse error: {exc}")
    try:
        req = CreateStoreRequest.model_validate(meta_dict)
    except Exception as exc:
        raise HTTPException(422, f"meta validation error: {exc}")

    supplemental_bytes: bytes | None = None
    if supplemental is not None:
        filename = supplemental.filename or ""
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in SUPPLEMENTAL_ALLOWED_EXTS:
            raise HTTPException(422, f"Unsupported supplemental format: {filename}. Use .csv or .xlsx.")
        if supplemental.size is not None and supplemental.size > SUPPLEMENTAL_MAX_BYTES:
            raise HTTPException(413, "Supplemental file is too large (max 10MB).")
        supplemental_bytes = await supplemental.read()
        if len(supplemental_bytes) > SUPPLEMENTAL_MAX_BYTES:
            raise HTTPException(413, "Supplemental file is too large (max 10MB).")

    return project_service.create_project_without_layout(
        config=get_config(),
        name=req.name.strip(),
        description=req.description,
        store_type=req.store_type.strip(),
        address=req.address.strip(),
        customer_profile=req.customer_profile.strip(),
        weekly_schedule=req.weekly_schedule,
        supplemental_bytes=supplemental_bytes,
        supplemental_filename=(supplemental.filename or "") if supplemental else "",
    )
