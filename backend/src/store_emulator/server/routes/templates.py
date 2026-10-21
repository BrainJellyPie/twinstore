"""Store-format templates: generate a complete, valid layout with a generic assortment."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from store_emulator.application.errors import AppError
from store_emulator.application.template_layouts import create_building_layouts, create_template_layout
from store_emulator.domain.layout_options import (
    BuildingFloorRequest, BuildingLayoutRequest, BuildingPreset, CheckoutPlacement, CheckoutWall, EntrancePosition, ExitPosition, FixtureDesign, LayoutDensity, LayoutOptions, LayoutPreset, LayoutStyle,
    GateWall, SeatingZone, ShelfDirection, StoreDesign, TemplateCategoryId, TemplateLayoutRequest,
)
from store_emulator.engine.layout_gen import TEMPLATES, generate_store, get_template
from store_emulator.engine.layout_gen.catalog import category_label
from store_emulator.domain.store import Store

router = APIRouter(prefix="/api", tags=["templates"])


class TemplateCategory(BaseModel):
    id: str
    label: str


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
    default_checkouts: int
    default_seating_zone: SeatingZone
    default_checkout_placement: CheckoutPlacement
    categories: list[TemplateCategory]


@router.get("/store-templates", summary="Store formats that can be generated", response_model=list[TemplateInfo])
def list_templates() -> list[TemplateInfo]:
    out: list[TemplateInfo] = []
    for t in TEMPLATES:
        s = generate_store(t.id, seed=0)
        out.append(TemplateInfo(
            id=t.id, name=t.name, description=t.description, store_type=t.store_type, grid=t.grid,
            racks=sum(1 for r in s.racks if r.slots), skus=len({i.sku for r in s.racks for sl in r.slots for i in sl.items}),
            open_hours=t.open_hours, default_style=t.style, default_design=s.design_theme,
            default_dining_tables=t.dining_tables, default_seating_zone=t.seating_zone,
            default_checkouts=t.checkouts,
            default_checkout_placement=t.checkout_placement,
            categories=[TemplateCategory(id=category, label=category_label(category, "USD"))
                        for category in sorted(set(t.fridges + t.freezers + t.wall_shelves + t.gondolas + t.near_counter))],
        ))
    return out


@router.get("/store-templates/{template_id}/preview", summary="Preview a generated store (not saved)")
def preview(
    template_id: str, seed: int = 0, currency: Literal["USD", "KRW", "JPY"] = "USD",
    style: LayoutStyle | None = None,
    width: int | None = Query(default=None, ge=8, le=40),
    height: int | None = Query(default=None, ge=6, le=40),
    density: LayoutDensity = "balanced", entrance: EntrancePosition = "left",
    aisle_width: int | None = Query(default=None, ge=1, le=4),
    max_shelf_run: int | None = Query(default=None, ge=1, le=8),
    exit_position: ExitPosition = "shared",
    gate_wall: GateWall = "front",
    shelf_direction: ShelfDirection = "horizontal",
    checkouts: int | None = Query(default=None, ge=1, le=12), fixture_design: FixtureDesign = "mixed",
    design_theme: StoreDesign | None = None,
    dining_tables: int | None = Query(default=None, ge=0, le=48),
    table_clearance: int = Query(default=1, ge=1, le=3),
    seating_zone: SeatingZone = "auto", checkout_placement: CheckoutPlacement = "auto",
    checkout_wall: CheckoutWall = "front",
    excluded_categories: list[TemplateCategoryId] | None = Query(default=None, max_length=64),
    products_per_category: int | None = Query(default=None, ge=1, le=16),
) -> Store:
    options = LayoutOptions(style=style, width=width, height=height, density=density, aisle_width=aisle_width, max_shelf_run=max_shelf_run,
                            shelf_direction=shelf_direction,
                            entrance=entrance, exit_position=exit_position, gate_wall=gate_wall, checkouts=checkouts, fixture_design=fixture_design,
                            design_theme=design_theme, dining_tables=dining_tables, table_clearance=table_clearance,
                            seating_zone=seating_zone, checkout_placement=checkout_placement, checkout_wall=checkout_wall,
                            excluded_categories=excluded_categories or [], products_per_category=products_per_category)
    return _preview_store(template_id, seed, currency, options)


@router.post("/store-templates/preview", summary="Preview a generated store with reserved areas (not saved)")
def preview_options(req: TemplateLayoutRequest) -> Store:
    return _preview_store(req.template_id, req.seed, req.currency, req)


@router.post("/store-templates/preset/validate", summary="Validate reusable layout options without saving a store", response_model_exclude_none=True)
def validate_preset(req: LayoutPreset) -> LayoutPreset:
    layout = req.layout.model_copy(update={"source_setup_id": None, "name": None})
    _preview_store(layout.template_id, layout.seed, layout.currency, layout)
    return req.model_copy(update={"layout": layout})


@router.post("/store-templates/building-preset/validate", summary="Validate reusable building options without saving floors", response_model_exclude_none=True)
def validate_building_preset(req: BuildingPreset) -> BuildingPreset:
    labels = [floor.label.casefold() for floor in req.floors]
    if len(set(labels)) != len(labels):
        raise HTTPException(422, "Floor labels must be unique within the building.")
    floors: list[BuildingFloorRequest] = []
    for level, floor in enumerate(req.floors, start=1):
        layout = floor.layout.model_copy(update={"source_setup_id": None, "name": None})
        try:
            _preview_store(layout.template_id, layout.seed, layout.currency, layout)
        except HTTPException as exc:
            raise HTTPException(exc.status_code, f"Floor {level} ({floor.label}): {exc.detail}") from exc
        floors.append(floor.model_copy(update={"layout": layout}))
    return req.model_copy(update={"floors": floors})


def _preview_store(template_id: str, seed: int, currency: str, options: LayoutOptions) -> Store:
    if get_template(template_id) is None:
        raise HTTPException(404, f"unknown template: {template_id}")
    try:
        return generate_store(template_id, seed=seed, currency=currency, options=options)
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
