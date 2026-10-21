"""File-backed field pilot plans; versioned imports and irreversible closure."""

import uuid
from pathlib import Path

from filelock import FileLock, Timeout

from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import _check_id  # pyright: ignore[reportPrivateUsage]
from store_emulator.application.staff_pitch import get_pitch
from store_emulator.application.storage.io import DATA_DIR, now_iso, read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.field_pilot import FieldPilot, PilotRequest, PilotSummary, PilotView
from store_emulator.domain.field_planning import PilotPlanningRequest, PilotPlanningResult
from store_emulator.engine.marketing.field_pilot import allocate_pilot, analyze_pilot, observations_csv, parse_observations
from store_emulator.engine.marketing.field_planning import plan_pilot


def _root(pid: str) -> Path:
    _check_id(pid, "project id")
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)
    return Path(DATA_DIR) / pid / "marketing" / "field-pilots"


def _path(pid: str, pilot_id: str) -> Path:
    _check_id(pilot_id, "pilot id")
    path = _root(pid) / pilot_id / "pilot.json"
    if not path.exists():
        raise AppError("Field pilot not found", 404)
    return path


def create_pilot(pid: str, pitch_id: str, req: PilotRequest) -> PilotView:
    root = _root(pid)
    source = get_pitch(pid, pitch_id).report
    if source is None:
        raise AppError("Complete a staff script screening test before preparing its field pilot", 409)
    pilot_id = f"pilot_{uuid.uuid4().hex[:12]}"
    now = now_iso()
    pilot = FieldPilot(pilot_id=pilot_id, pitch_id=pitch_id, created_at=now, updated_at=now, design=req,
                       product=source.product.model_copy(deep=True), variants=source.request.variants,
                       context=source.request.context, product_facts=source.request.product_facts,
                       assignments=allocate_pilot(pilot_id, req),
                       planning=plan_pilot(PilotPlanningRequest(assumptions=req.planning,
                                           block_counts=[b.encounters for b in req.blocks])) if req.planning else None)
    write_json(root / pilot_id / "pilot.json", pilot.model_dump(mode="json"))
    return PilotView(pilot=pilot, analysis=analyze_pilot(pilot))


def preview_plan(pid: str, req: PilotPlanningRequest) -> PilotPlanningResult:
    _root(pid)
    return plan_pilot(req)


def list_pilots(pid: str) -> list[PilotSummary]:
    result: list[PilotSummary] = []
    for path in _root(pid).glob("*/pilot.json"):
        pilot = FieldPilot.model_validate(read_json(path))
        result.append(PilotSummary(pilot_id=pilot.pilot_id, pitch_id=pilot.pitch_id, name=pilot.design.name,
                                   created_at=pilot.created_at, finalized_at=pilot.finalized_at,
                                   planned=len(pilot.assignments), enrolled=sum(a.enrolled is True for a in pilot.assignments)))
    return sorted(result, key=lambda item: item.created_at, reverse=True)


def get_pilot(pid: str, pilot_id: str) -> PilotView:
    pilot = FieldPilot.model_validate(read_json(_path(pid, pilot_id)))
    return PilotView(pilot=pilot, analysis=analyze_pilot(pilot))


def export_observations(pid: str, pilot_id: str) -> str:
    return observations_csv(get_pilot(pid, pilot_id).pilot)


def import_observations(pid: str, pilot_id: str, data: bytes, revision: int) -> PilotView:
    path = _path(pid, pilot_id)
    try:
        with FileLock(path.with_suffix(".lock"), timeout=0):
            pilot = FieldPilot.model_validate(read_json(path))
            if pilot.finalized_at:
                raise AppError("This field pilot is closed; its observations are locked", 409)
            if pilot.revision != revision:
                raise AppError("The pilot changed in another session. Reload it before importing", 409)
            try:
                assignments = parse_observations(data, pilot)
            except ValueError as exc:
                raise AppError(str(exc), 400) from exc
            pilot.assignments = assignments
            pilot.revision += 1
            pilot.updated_at = now_iso()
            write_json(path, pilot.model_dump(mode="json"))
    except Timeout as exc:
        raise AppError("Another field pilot update is in progress; reload and retry", 409) from exc
    return PilotView(pilot=pilot, analysis=analyze_pilot(pilot))


def finalize_pilot(pid: str, pilot_id: str, revision: int) -> PilotView:
    path = _path(pid, pilot_id)
    try:
        with FileLock(path.with_suffix(".lock"), timeout=0):
            pilot = FieldPilot.model_validate(read_json(path))
            if pilot.revision != revision or pilot.finalized_at:
                raise AppError("The pilot changed or is already closed; reload it", 409)
            if not analyze_pilot(pilot).can_finalize:
                raise AppError("Record every slot as enrolled or unused, and complete delivery and purchase outcomes for enrolled encounters", 409)
            pilot.finalized_at = now_iso()
            pilot.updated_at = pilot.finalized_at
            pilot.revision += 1
            write_json(path, pilot.model_dump(mode="json"))
    except Timeout as exc:
        raise AppError("Another field pilot update is in progress; reload and retry", 409) from exc
    return PilotView(pilot=pilot, analysis=analyze_pilot(pilot))
