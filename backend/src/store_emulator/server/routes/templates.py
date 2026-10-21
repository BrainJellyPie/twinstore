"""Store-format templates: generate a complete, valid layout with a generic assortment."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from store_emulator.application.errors import AppError
from store_emulator.application.template_layouts import create_building_layouts, create_template_layout
from store_emulator.domain.layout_options import (
    BuildingLayoutRequest, EntrancePosition, FixtureDesign, LayoutDensity, LayoutOptions, LayoutStyle,
    StoreDesign, TemplateLayoutRequest,
)
from store_emulator.engine.layout_gen import TEMPLATES, generate_store, get_template

router = APIRouter(prefix="/api", tags=["templates"])


class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    store_type: str
    grid: tuple[int, int]
    racks: int
    skus: int
    open_hours: tuple[int, int]
    default_design: StoreDesign
    default_style: LayoutStyle
    default_dining_tables: int


@router.get("/store-templates", summary="Store formats that can be generated", response_model=list[TemplateInfo])
def list_templates() -> list[TemplateInfo]:
    out: list[TemplateInfo] = []
    for t in TEMPLATES:
        s = generate_store(t.id, seed=0)
        out.append(TemplateInfo(
            id=t.id, name=t.name, description=t.description, store_type=t.store_type, grid=t.grid,
            racks=sum(1 for r in s.racks if r.slots), skus=len({i.sku for r in s.racks for sl in r.slots for i in sl.items}),
            open_hours=t.open_hours, default_style=t.style, default_design=s.design_theme,
            default_dining_tables=t.dining_tables,
        ))
    return out


@router.get("/store-templates/{template_id}/preview", summary="Preview a generated store (not saved)")
def preview(
    template_id: str, seed: int = 0, currency: Literal["USD", "KRW", "JPY"] = "USD",
    style: LayoutStyle | None = None,
    width: int | None = Query(default=None, ge=8, le=40),
    height: int | None = Query(default=None, ge=6, le=40),
    density: LayoutDensity = "balanced", entrance: EntrancePosition = "left",
    checkouts: int = Query(default=1, ge=1, le=4), fixture_design: FixtureDesign = "mixed",
    design_theme: StoreDesign | None = None,
    dining_tables: int | None = Query(default=None, ge=0, le=12),
) -> dict[str, Any]:
    if get_template(template_id) is None:
        raise HTTPException(404, f"unknown template: {template_id}")
    options = LayoutOptions(style=style, width=width, height=height, density=density,
                            entrance=entrance, checkouts=checkouts, fixture_design=fixture_design,
                            design_theme=design_theme, dining_tables=dining_tables)
    try:
        return generate_store(template_id, seed=seed, currency=currency, options=options).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/projects/{pid}/setups/generate", summary="New layout from a store-format template")
def generate_layout(pid: str, req: TemplateLayoutRequest) -> dict[str, object]:
    """Creates a draft layout with fixtures and a full generic assortment; edit it like any layout."""
    try:
        return create_template_layout(pid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/projects/{pid}/setups/generate-building", summary="Create linked layouts for a multi-floor store")
def generate_building(pid: str, req: BuildingLayoutRequest) -> dict[str, object]:
    """Each floor is editable and simulated independently. Cross-floor travel is not simulated."""
    try:
        setups = create_building_layouts(pid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"setups": setups, "active_setup_id": setups[0]["id"]}
