"""Store-format templates: generate a complete, valid layout with a generic assortment."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from store_emulator.application.setups import set_active_setup, setup_summary
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, setup_dir, setup_path
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


class GenerateLayoutRequest(BaseModel):
    template_id: str
    seed: int = 0
    currency: str = Field(default="USD", description="USD (English names) or KRW (Korean names, won prices)")
    style: Literal["aisles", "loop"] | None = None
    name: str | None = None


@router.get("/store-templates", summary="Store formats that can be generated", response_model=list[TemplateInfo])
def list_templates() -> list[TemplateInfo]:
    out: list[TemplateInfo] = []
    for t in TEMPLATES:
        s = generate_store(t.id, seed=0)
        out.append(TemplateInfo(
            id=t.id, name=t.name, description=t.description, store_type=t.store_type, grid=t.grid,
            racks=sum(1 for r in s.racks if r.slots), skus=len({i.sku for r in s.racks for sl in r.slots for i in sl.items}),
            open_hours=t.open_hours,
        ))
    return out


@router.get("/store-templates/{template_id}/preview", summary="Preview a generated store (not saved)")
def preview(template_id: str, seed: int = 0, currency: str = "USD", style: Literal["aisles", "loop"] | None = None) -> dict[str, Any]:
    if get_template(template_id) is None:
        raise HTTPException(404, f"unknown template: {template_id}")
    return generate_store(template_id, seed=seed, currency=currency, style=style).model_dump(mode="json")


@router.post("/projects/{pid}/setups/generate", summary="New layout from a store-format template")
def generate_layout(pid: str, req: GenerateLayoutRequest) -> dict[str, Any]:
    """Creates a draft layout with fixtures and a full generic assortment; edit it like any layout."""
    template = get_template(req.template_id)
    if template is None:
        raise HTTPException(404, f"unknown template: {req.template_id}")
    if not setup_dir(pid).parent.is_dir():
        raise HTTPException(404, f"project not found: {pid}")
    store = generate_store(req.template_id, seed=req.seed, currency=req.currency, style=req.style,
                           store_id=f"store_{pid}", name=req.name or template.name)
    setup = new_setup_data(req.name or template.name, None, store.model_dump(mode="json"),
                           memo=f"Generated from template '{template.name}' (seed {req.seed}, {req.currency})")
    write_json(setup_path(pid, setup["id"]), setup)
    set_active_setup(pid, setup["id"])
    return setup_summary(pid, setup)
