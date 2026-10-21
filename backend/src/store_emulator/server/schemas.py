from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from store_emulator.domain.store import DaySchedule
from store_emulator.domain.layout_options import BuildingFloorInfo, TemplateLayoutRequest
from store_emulator.domain.types import Face
from store_emulator.engine.validation import BlockedFaceDetail, ClearedSlot, Issue


class CreateStoreRequest(BaseModel):
    """Input schema for POST /api/projects/create-store. Validation lives here so API bypass is blocked."""
    name: str
    description: str = ""
    address: str
    store_type: str
    customer_profile: str
    weekly_schedule: list[DaySchedule]
    layout: TemplateLayoutRequest | None = None

    @field_validator("name", "address", "store_type", "customer_profile")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class SimulationStartResponse(BaseModel):
    project_id: str
    run_id: str
    setup_id: str


ReadinessReason = Literal[
    "layout_pending", "personas_pending", "no_layout", "no_personas", "no_items",
    "no_entrance", "no_exit", "no_counter",
]


class Readiness(BaseModel):
    ready: bool
    reasons: list[ReadinessReason] = Field(default_factory=lambda: list[ReadinessReason]())


GenerationKind = Literal["layout", "persona"]
GenerationStatusValue = Literal["pending", "running", "completed", "failed"]


class GenerationStatusModel(BaseModel):
    status: GenerationStatusValue
    kind: GenerationKind
    setup_id: str
    error: str | None = None
    progress: dict[str, object] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GenerationListItem(GenerationStatusModel):
    gen_id: str


class RegeneratePersonaResponse(BaseModel):
    """Response for `POST /api/projects/{pid}/setups/{sid}/regenerate-persona`.

    Signals that a persona regeneration job has started and returns the
    polling ``gen_id``.
    """
    gen_id: str


class ClearedSlotInfo(BaseModel):
    """Detail of a slot auto-removed after upload/save.

    The backend distinguishes four internal reasons (locked / out_of_bounds /
    occupied / unreachable) but collapses them to a single ``"blocked"`` in
    the response.
    """
    rack_id: str = Field(description="rack identifier")
    block: int = Field(description="rack block index (0-based, rotated frame)")
    face: Face = Field(description="block's exposed face (N/S/E/W)")
    level: int = Field(description="level (1~4)")
    cleared_skus: list[str] = Field(
        default_factory=lambda: list[str](),
        description="all SKUs in the removed slot (supports multi-SKU per slot)",
    )
    name: str = Field(description="display name of the removed slot's item")
    reason: Literal["blocked"] = Field(
        default="blocked",
        description="unified value 'blocked'. Internal classification (locked/out_of_bounds/occupied/unreachable) is visible only in backend logs",
    )

    @classmethod
    def from_cleared(cls, c: ClearedSlot) -> "ClearedSlotInfo":
        return cls(
            rack_id=c.rack_id, block=c.block, face=c.face,
            level=c.level, cleared_skus=list(c.cleared_skus), name=c.name,
        )


class BlockedSlotFaceInfo(BaseModel):
    """An (rack_id, block, face) tuple that the Excel template must pre-exclude.

    Response shape for ``POST /api/util/blocked-faces`` (body: ``{store}``).
    The frontend uses this set to drop all four level rows (level 1-4) at once.
    """
    rack_id: str = Field(description="rack identifier")
    block: int = Field(description="rack block index (0-based, rotated frame)")
    face: Face = Field(description="unreachable exposed face (N/S/E/W)")
    reason: Literal["blocked"] = Field(
        default="blocked",
        description="unified value 'blocked'. Internal classification is not exposed in the response",
    )

    @classmethod
    def from_detail(cls, d: BlockedFaceDetail) -> "BlockedSlotFaceInfo":
        return cls(rack_id=d.rack_id, block=d.block, face=d.face)


class ReplaceSlotsResponse(BaseModel):
    count: int = Field(
        description="number of registered SKU placements (sum of SKUs per slot). "
        "When multiple SKUs share a coordinate they are summed accordingly.",
    )
    cleared: list[ClearedSlotInfo] = Field(
        default_factory=lambda: list[ClearedSlotInfo](),
        description="auto-removed unreachable slot details. An empty array means every row was registered successfully.",
    )


class SetupSummary(BaseModel):
    """Setup summary (store excluded). Shared by list, PUT response, and projects response.

    Extra fields (store, readiness extras, ...) are ignored so dicts from
    ``get_setup`` and friends round-trip safely through ``model_validate``.
    """
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    status: str
    parentId: str | None
    runId: str | None
    memo: str
    created_at: str
    updated_at: str
    readiness: Readiness | None = None
    building: BuildingFloorInfo | None = None
    generation: dict[str, object] | None = None


class SetupDetail(SetupSummary):
    """Response for GET /setups/{sid} — includes store and blocked_faces (spec rev 4 §4.1)."""
    store: dict[str, object] | None = None
    blocked_faces: list[BlockedFaceDetail] = Field(
        default_factory=lambda: list[BlockedFaceDetail](),
    )


class SaveSetupResponse(BaseModel):
    """Response for `PUT /api/projects/{pid}/setups/{sid}` (spec rev 4 §4.1).

    Bundles slots auto-removed on save (unreachable), blocked faces, and
    validation issues so the client gets everything in one shot.
    """
    setup: SetupSummary
    cleared: list[ClearedSlotInfo] = Field(
        default_factory=lambda: list[ClearedSlotInfo](),
    )
    blocked_faces: list[BlockedFaceDetail] = Field(
        default_factory=lambda: list[BlockedFaceDetail](),
    )
    issues: list[Issue] = Field(default_factory=lambda: list[Issue]())


class SetupUpdatePayload(BaseModel):
    """Inner body of SaveSetupRequest. Partial update — only the supplied fields among name/store/memo are applied."""
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    store: dict[str, object] | None = None
    memo: str | None = None


class SaveSetupRequest(BaseModel):
    """Request body for `PUT /api/projects/{pid}/setups/{sid}` (spec rev 4 §4.1, nested shape)."""
    model_config = ConfigDict(extra="ignore")

    setup: SetupUpdatePayload


class ProjectMetadata(BaseModel):
    project_id: str
    name: str
    description: str = ""
    store_type: str
    currency: str | None = None
    grid_size: list[int] | None = None
    weekly_schedule: list[dict[str, object]] = Field(default_factory=lambda: list[dict[str, object]]())
    address: str = ""
    customer_profile: str = ""
    supplemental_summary: str = ""
    created_at: str
    updated_at: str


class ProjectWithLayoutResponse(BaseModel):
    metadata: ProjectMetadata
    setup: SetupSummary
    layoutGenId: str


class CreateStoreResponse(BaseModel):
    metadata: ProjectMetadata
    setup: SetupSummary
    personaGenId: str


class StatusResponse(BaseModel):
    status: str


class DeletedResponse(BaseModel):
    status: str
    deleted: list[str]


class EngineInfo(BaseModel):
    """A simulation engine selectable per run."""
    engine_type: str
    label: str
    description: str
    uses_llm: bool
    model: str = ""
    default: bool = False
