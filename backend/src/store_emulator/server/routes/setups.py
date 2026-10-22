from typing import Any, Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from store_emulator.application import layout_edit
from store_emulator.application import setups as setup_service
from store_emulator.application import generation_async
from store_emulator.application.errors import AppError
from store_emulator.application.storage.generations import read_status
from store_emulator.engine.layout_edit import LayoutEditDraft
from store_emulator.domain.types import ResourceId
from store_emulator.server.deps import get_config
from store_emulator.server.schemas import (
    ClearedSlotInfo,
    DeletedResponse,
    GenerationListItem,
    GenerationStatusModel,
    RegeneratePersonaResponse,
    ReplaceSlotsResponse,
    SaveSetupRequest,
    SaveSetupResponse,
    SetupDetail,
    SetupSummary,
)

router = APIRouter(prefix="/api/projects/{pid}/setups", tags=["setups"])


def _http_exc_from_app_error(e: AppError) -> HTTPException:
    """spec rev 4 §4.1 wire shape: {detail: {code, reason, message, details}}."""
    return HTTPException(
        status_code=e.status_code,
        detail={
            "code": e.code,
            "reason": e.reason,
            "message": e.message,
            "details": e.details,
        },
    )


class SlotInputRow(BaseModel):
    rack_id: str = Field(description="rack identifier (must exist in setup.store)")
    block: int = Field(description="rack block index (0-based, rotated frame)")
    face: str = Field(description="block's exposed face. One of N/S/E/W")
    level: int = Field(description="level (1~4 range)")
    sku: str = Field(default="", description="item SKU. Empty value means the slot is treated as empty and excluded from the registered count")
    name: str = Field(default="", description="display name for the SKU")
    price: int = Field(default=0, ge=0, description="unit: US cents (e.g. 549 = $5.49)")
    promo: str = Field(default="", description="promotion label for the SKU")


class ReplaceSlotsRequest(BaseModel):
    slots: list[SlotInputRow] = Field(
        default_factory=lambda: list[SlotInputRow](),
        description="all slot rows to register into setup.store. Rows with empty SKU are treated as empty slots",
    )


class CreateSetupRequest(BaseModel):
    """Setup creation request. Whether `source_setup_id` is required depends on `mode`.

    - racks_and_items / racks: `source_setup_id` required (clone).
    - empty: `source_setup_id` optional (used as parentId if given; otherwise root setup).
    """
    mode: Literal["racks_and_items", "racks", "empty"] = Field(description="generation mode")
    source_setup_id: ResourceId | None = Field(
        default=None,
        description="source setup id to copy from. Optional when mode=empty.",
    )
    name: str | None = None
    memo: str = ""


@router.get("", summary="List setups")
async def get_setups(pid: str) -> list[dict[str, Any]]:
    """List setup summaries (store excluded). Sorted by `updated_at` descending.

    **Response fields:** id, name, status(draft/running/locked), parentId, runId, memo, readiness, created_at, updated_at."""
    return setup_service.get_setups(pid)


@router.get("/{sid}", summary="Get setup", response_model=SetupDetail)
async def get_setup(pid: str, sid: str) -> SetupDetail:
    """Load the full setup (store + blocked_faces, spec rev 4 §4.1).

    `blocked_faces` is pre-computed via `list_blocked_faces` so the client can
    obtain the Excel-template exclusion set without an extra call.
    `readiness` is also computed inside ``load_setup_with_validation`` so the
    whole response is produced in a single read.
    """
    try:
        result = setup_service.load_setup_with_validation(pid, sid)
    except AppError as e:
        raise _http_exc_from_app_error(e)
    return SetupDetail.model_validate(result)


@router.put("/{sid}", summary="Save setup", response_model=SaveSetupResponse)
async def save_setup(pid: str, sid: str, req: SaveSetupRequest) -> SaveSetupResponse:
    """Save the setup (partial update of store / name / memo, spec rev 4 §4.1).

    - **store change:** only when runId is absent. If items are registered,
      rack changes are rejected (409 racks_locked). Slots on faces that become
      unreachable at save time are auto-removed and reported in `cleared`.
    - **name/memo change:** blocked only when runId is present (locked).
    - Slot registration uses a separate route: `PUT /setups/{sid}/slots`.

    **Response (`SaveSetupResponse`):**
    - `setup`: setup summary after save
    - `cleared`: auto-removed slots; empty array if none
    - `blocked_faces`: unreachable face list after save
    - `issues`: severity=warning only (errors short-circuit to 422)

    **Errors:** 404 setup_not_found, 409 setup_locked / racks_locked,
    422 invalid_store / validation_failed, 503 setup_lock_timeout.
    """
    payload: dict[str, object] = req.setup.model_dump(exclude_unset=True)
    try:
        result = await run_in_threadpool(
            setup_service.save_setup_with_lock, pid, sid, payload,
        )
    except AppError as e:
        raise _http_exc_from_app_error(e)
    return SaveSetupResponse.model_validate(result)


@router.put("/{sid}/slots", summary="Bulk replace slots (Excel upload)", response_model=ReplaceSlotsResponse)
async def replace_slots(pid: str, sid: str, req: ReplaceSlotsRequest) -> ReplaceSlotsResponse:
    """Replace all slots on a draft setup. Single entry point for Excel upload.

    **Validation (400 on failure):**
    - Each (rack_id, block, face, level) must exist in setup.store
    - Coordinates falling on locked_faces are rejected
    - level must be in 1..RACK_LEVELS
    - block/face/level format errors

    Multiple rows sharing the same (rack_id, block, face, level) accumulate as
    SlotItems; each SKU keeps its own name/price/promo. No cross-row uniqueness
    check is performed.

    Rows with empty sku ("") produce no SlotItem; if a coordinate ends up with
    no non-empty items, no Slot is created either (sparse representation).

    **Automatic handling:** validated slots on unreachable faces are auto-removed
    and reported via `cleared`.

    **Response:** `ReplaceSlotsResponse`
    - `count`: number of SKU placements registered (sum of slot.items)
    - `cleared`: auto-removed slot details (`ClearedSlotInfo[]`); empty array means everything was registered cleanly.

    **Errors:** 400 (coord/level/face format failure), 404 (setup not found), 409 (not draft / layout generation in progress).

    **Recommended workflow:** call `POST /api/util/blocked-faces` (body: `{store}`)
    first to obtain the unreachable face list, exclude those cells from the Excel
    template before the user fills it in, and `cleared` will stay near-empty.
    """
    try:
        result = setup_service.replace_slots(pid, sid, [r.model_dump() for r in req.slots])
    except AppError as e:
        raise HTTPException(e.status_code, str(e))
    return ReplaceSlotsResponse(
        count=result.count,
        cleared=[ClearedSlotInfo.from_cleared(c) for c in result.cleared],
    )




@router.post("", summary="Create setup (clone existing)", response_model=SetupSummary)
async def create_setup(pid: str, req: CreateSetupRequest) -> dict[str, Any]:
    """Create a setup. Depending on `mode`, either clones or creates an empty setup.

    - racks_and_items / racks: copy the store from `source_setup_id` into a new draft.
    - empty: empty setup with store=None; `source_setup_id`, if provided, is used as parentId.

    **Returns:** new setup summary (store excluded, readiness included)."""
    try:
        return setup_service.create_setup_from_source(
            pid, req.source_setup_id, req.mode, req.name, req.memo,
        )
    except AppError as e:
        raise HTTPException(e.status_code, str(e))


@router.get("/{sid}/generations/{gid}/status", summary="Poll generation status", response_model=GenerationStatusModel)
async def get_generation_status(pid: str, sid: str, gid: str) -> dict[str, Any]:
    """Progress status for async layout/persona generation.

    **Response:** `{status, kind, setup_id, error, progress, created_at, updated_at}`.
    status: pending → running → completed | failed.

    **Errors:**
    - 404: gen_id not found
    - 404: gen_id belongs to a different setup (URL `sid` mismatches `status.setup_id`)"""
    try:
        data = read_status(pid, gid)
    except FileNotFoundError:
        raise HTTPException(404, "generation not found")
    if data.get("setup_id") != sid:
        raise HTTPException(404, "no generation found for this setup")
    return data


@router.get("/{sid}/generations", summary="List generations for setup", response_model=list[GenerationListItem])
async def list_setup_generations(
    pid: str, sid: str, active_only: bool = False,
) -> list[dict[str, Any]]:
    """Generation history scoped to a setup. With `active_only=true`, returns only pending/running.

    Used when re-entering a project to discover in-progress generations and resume polling."""
    from store_emulator.application.storage.generations import list_generations as _list
    items = _list(pid, sid)
    if active_only:
        items = [i for i in items if i.get("status") in ("pending", "running")]
    return items


@router.post(
    "/{sid}/regenerate-persona",
    summary="Trigger persona regeneration",
    response_model=RegeneratePersonaResponse,
)
async def regenerate_persona(pid: str, sid: str) -> RegeneratePersonaResponse:
    """Manually trigger persona generation. Used when the persona step in the
    automatic layout chain fails.

    **Errors:**
    - 404: setup not found
    - 409: a simulation is running, simulation history exists, this setup has an active generation,
      or persona generation is active anywhere in the project
    """
    try:
        gen_id = generation_async.start_persona_generation(
            get_config(), pid, sid,
        )
    except FileNotFoundError:
        raise HTTPException(404, f"setup not found: {sid}")
    except AppError as e:
        raise HTTPException(e.status_code, str(e))
    return RegeneratePersonaResponse(gen_id=gen_id)


@router.delete("/{sid}", summary="Delete setup", response_model=DeletedResponse)
async def delete_setup_endpoint(pid: str, sid: str) -> DeletedResponse:
    """Delete a setup along with all descendant branches.

    **Constraints:** the root setup (parentId=null) cannot be deleted (409). A
    setup in `running` state cannot be deleted (409). If the deleted setup was
    active, the first remaining setup becomes active automatically."""
    try:
        deleted_ids = setup_service.delete_setup_with_descendants(pid, sid)
    except AppError as e:
        raise HTTPException(e.status_code, str(e))
    return DeletedResponse(status="deleted", deleted=deleted_ids)


@router.post("/{sid}/edit/draft", summary="Draft layout edits from instructions", response_model=LayoutEditDraft)
async def draft_layout_edit(pid: str, sid: ResourceId, req: layout_edit.LayoutEditRequest) -> LayoutEditDraft:
    """The text model turns instructions ("put the cola at eye level, 10 % off ice cream") into price, discount, sign,
    move and category-price edits on this layout's products and shelves, checked on a copy. Nothing is saved."""
    try:
        return await run_in_threadpool(layout_edit.draft_edit, pid, sid, req, get_config())
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e


@router.post("/{sid}/edit", summary="Save layout edits as a new layout")
async def apply_layout_edit(pid: str, sid: ResourceId, req: layout_edit.LayoutEditApply) -> dict[str, Any]:
    """Apply the reviewed edits to this layout and save the result as a new, active layout; the original stays as it
    is. **Returns:** the new setup summary with `applied` (the edits in words) and `warnings`."""
    try:
        return await run_in_threadpool(layout_edit.apply_edit, pid, sid, req)
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e
