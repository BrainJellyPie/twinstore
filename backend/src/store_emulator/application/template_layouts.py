"""Create editable template layouts and linked, independently simulated building floors."""

import uuid
from pathlib import Path

from store_emulator.application.errors import AppError
from store_emulator.application.setups import set_active_setup, setup_summary
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, new_setup_data, setup_path
from store_emulator.domain.layout_options import (
    BuildingFloorInfo, BuildingLayoutRequest, LayoutOptions, TemplateLayoutRequest,
)
from store_emulator.engine.layout_gen import generate_store, get_template


def prepare_template_layout(pid: str, req: TemplateLayoutRequest) -> dict[str, object]:
    template = get_template(req.template_id)
    if template is None:
        raise AppError(f"unknown template: {req.template_id}", 404)
    options = LayoutOptions.model_validate(req.model_dump(include=set(LayoutOptions.model_fields)))
    name = req.name or template.name
    try:
        store = generate_store(req.template_id, seed=req.seed, currency=req.currency, options=options,
                               store_id=f"store_{pid}", name=name)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc
    memo = f"Generated from template '{template.name}' (seed {req.seed}, {req.currency})"
    memo += f"\nLayout options: {options.model_dump_json()}"
    if req.requirements.strip():
        memo += f"\nDesign brief (for manual editing): {req.requirements.strip()}"
    setup: dict[str, object] = new_setup_data(name, None, store.model_dump(mode="json"), memo=memo)
    setup["generation"] = req.model_dump(mode="json")
    return setup


def _persist(pid: str, setups: list[dict[str, object]]) -> list[dict[str, object]]:
    written: list[Path] = []
    try:
        for setup in setups:
            path = setup_path(pid, str(setup["id"]))
            written.append(path)
            write_json(path, setup)
        set_active_setup(pid, str(setups[0]["id"]))
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return [setup_summary(pid, setup) for setup in setups]


def create_template_layout(pid: str, req: TemplateLayoutRequest) -> dict[str, object]:
    if not metadata_path(pid).is_file():
        raise AppError(f"project not found: {pid}", 404)
    return _persist(pid, [prepare_template_layout(pid, req)])[0]


def create_building_layouts(pid: str, req: BuildingLayoutRequest) -> list[dict[str, object]]:
    if not metadata_path(pid).is_file():
        raise AppError(f"project not found: {pid}", 404)
    labels = [floor.label.casefold() for floor in req.floors]
    if len(set(labels)) != len(labels):
        raise AppError("floor labels must be unique within the building", 422)
    building_id = f"building_{uuid.uuid4().hex}"
    setups: list[dict[str, object]] = []
    # Prepare every floor before writing: an invalid upper floor cannot leave half a building.
    for level, floor in enumerate(req.floors, start=1):
        layout = TemplateLayoutRequest.model_validate({**floor.layout.model_dump(), "name": f"{req.name} · {floor.label}"})
        setup = prepare_template_layout(pid, layout)
        setup["building"] = BuildingFloorInfo(id=building_id, name=req.name, level=level,
                                              label=floor.label, floor_count=len(req.floors)).model_dump()
        setup["memo"] = f"{setup['memo']}\nBuilding floor {level}/{len(req.floors)}. Simulated independently; no travel between floors."
        setups.append(setup)
    return _persist(pid, setups)
