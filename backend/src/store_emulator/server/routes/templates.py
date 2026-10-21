"""Store-format templates: generate a complete, valid layout with a generic assortment."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from store_emulator.application.setups import set_active_setup, setup_summary
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import (
    new_setup_data,
    setup_dir,
    setup_path,
)
from store_emulator.domain.layout_options import (
    EntrancePosition, FixtureDesign, LayoutDensity, LayoutOptions, LayoutStyle,
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
    default_style: LayoutStyle


class GenerateLayoutRequest(LayoutOptions):
    template_id: str
    seed: int = 0
    currency: Literal["USD", "KRW", "JPY"] = "USD"
    name: str | None = Field(default=None, max_length=200)
    requirements: str = Field(default="", max_length=2000)


@router.get("/store-templates", summary="Store formats that can be generated", response_model=list[TemplateInfo])
def list_templates() -> list[TemplateInfo]:
    out: list[TemplateInfo] = []
    for t in TEMPLATES:
        s = generate_store(t.id, seed=0)
        out.append(TemplateInfo(
            id=t.id, name=t.name, description=t.description, store_type=t.store_type, grid=t.grid,
            racks=sum(1 for r in s.racks if r.slots), skus=len({i.sku for r in s.racks for sl in r.slots for i in sl.items}),
            open_hours=t.open_hours, default_style=t.style,
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
) -> dict[str, Any]:
    if get_template(template_id) is None:
        raise HTTPException(404, f"unknown template: {template_id}")
    options = LayoutOptions(style=style, width=width, height=height, density=density,
                            entrance=entrance, checkouts=checkouts, fixture_design=fixture_design)
    return generate_store(template_id, seed=seed, currency=currency, options=options).model_dump(mode="json")


@router.post("/projects/{pid}/setups/generate", summary="New layout from a store-format template")
def generate_layout(pid: str, req: GenerateLayoutRequest) -> dict[str, Any]:
    """Creates a draft layout with fixtures and a full generic assortment; edit it like any layout."""
    template = get_template(req.template_id)
    if template is None:
        raise HTTPException(404, f"unknown template: {req.template_id}")
    if not setup_dir(pid).parent.is_dir():
        raise HTTPException(404, f"project not found: {pid}")
    options = LayoutOptions.model_validate(req.model_dump(include=set(LayoutOptions.model_fields)))
    store = generate_store(req.template_id, seed=req.seed, currency=req.currency, options=options,
                           store_id=f"store_{pid}", name=req.name or template.name)
    memo = f"Generated from template '{template.name}' (seed {req.seed}, {req.currency})"
    memo += f"\nLayout options: {options.model_dump_json()}"
    if req.requirements.strip():
        memo += f"\nDesign brief (for manual editing): {req.requirements.strip()}"
    setup = new_setup_data(req.name or template.name, None, store.model_dump(mode="json"), memo=memo)
    setup["generation"] = req.model_dump(mode="json")
    write_json(setup_path(pid, setup["id"]), setup)
    set_active_setup(pid, setup["id"])
    return setup_summary(pid, setup)
