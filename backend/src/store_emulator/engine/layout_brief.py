"""A layout design brief read into the generator's own options.

"A calm pharmacy with a consultation corner at the back, two tills by the door, no alcohol, sage and white" becomes
the options the procedural generator understands (style, density, size, entrance, tills, theme, colors, seating,
excluded categories). What the options cannot express is listed instead of being guessed, so the brief stays the
record of what was asked and the options the record of what will be built.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from store_emulator.domain.layout_options import (
    CheckoutPlacement,
    CheckoutWall,
    EntrancePosition,
    GateWall,
    LayoutDensity,
    LayoutOptions,
    LayoutStyle,
    SeatingZone,
    ShelfDirection,
    StoreDesign,
)
from store_emulator.engine.prompting import resolve_listed

_HEX = re.compile(r"#[0-9a-fA-F]{6}")


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Colors(BaseModel):
    wall: str | None = Field(default=None, description="#rrggbb")
    floor: str | None = Field(default=None, description="#rrggbb")
    accent: str | None = Field(default=None, description="#rrggbb")
    counter: str | None = Field(default=None, description="#rrggbb")


class _Brief(BaseModel):
    style: LayoutStyle | None = None
    density: LayoutDensity | None = None
    width: int | None = Field(default=None, description="floor width in grid cells, only when the brief asks for a size")
    depth: int | None = Field(default=None, description="floor depth in grid cells, only when the brief asks for a size")
    aisle_width: int | None = Field(default=None, description="aisle width in grid cells, 1 to 4")
    shelf_direction: ShelfDirection | None = None
    entrance: EntrancePosition | None = Field(default=None, description="where the door is along its wall")
    gate_wall: GateWall | None = Field(default=None, description="the wall with the door")
    checkouts: int | None = Field(default=None, description="number of tills, 1 to 12")
    checkout_placement: CheckoutPlacement | None = None
    checkout_wall: CheckoutWall | None = None
    design_theme: StoreDesign | None = None
    design_colors: _Colors | None = None
    dining_tables: int | None = Field(default=None, description="tables for eating in, 0 to 48")
    seating_zone: SeatingZone | None = None
    excluded_categories: list[str] = Field(default_factory=list[str], description="listed categories the brief rules out")
    products_per_category: int | None = Field(default=None, description="products per category, 1 to 16")
    not_expressible: list[str] = Field(default_factory=list[str], max_length=8,
                                       description="parts of the brief none of these options can express, in a few words")
    rationale: str = Field(default="", max_length=500)


class BriefReading(BaseModel):
    options: dict[str, Any] = {}      # a patch of LayoutOptions fields, valid against the current options
    applied: list[str] = []           # each option in words
    not_expressible: list[str] = []
    warnings: list[str] = []
    rationale: str = ""


BRIEF_PROMPT = """You set up a procedural store-layout generator from a designer's brief. The store format is given
below with its default size, tills and product categories. Set only the options the brief asks for and leave every
other one empty (the format's default):
- style: aisles (parallel aisles), loop (racetrack), spine (one central walkway), cross (crossing aisles), plaza (open
  centre with fixtures around), free_flow (islands), perimeter (shelves on the walls, open centre), showroom (grouped
  displays);
- density: spacious, balanced or dense; aisle_width in grid cells (1 to 4); shelf_direction horizontal or vertical;
- size: width (8 to 40) and depth (6 to 40) in grid cells, only when the brief asks for a bigger, smaller or given
  size, scaled from the format's default;
- door: gate_wall (front, back, left, right) and entrance (left, center, right along that wall);
- tills: checkouts (how many), checkout_placement (near_entrance, away_from_entrance), checkout_wall;
- look: design_theme (classic, warm, minimal, industrial, botanical, luxury, coastal, terracotta, nordic, retro) and
  design_colors as #rrggbb for wall, floor, accent and counter when the brief names colors;
- eating in: dining_tables and seating_zone;
- assortment: excluded_categories from the listed categories (written as listed) when the brief rules them out, and
  products_per_category for a narrower or wider range.
Put anything the options cannot express (lighting, music, signage text, a specific fixture) in not_expressible, in a
few words each, and give a short rationale. Write in English."""

_LABELS = {
    "style": "Style", "density": "Density", "width": "Width", "height": "Depth", "aisle_width": "Aisle width",
    "shelf_direction": "Shelf direction", "entrance": "Entrance", "gate_wall": "Door wall", "checkouts": "Tills",
    "checkout_placement": "Till placement", "checkout_wall": "Till wall", "design_theme": "Theme",
    "design_colors": "Colors", "dining_tables": "Dining tables", "seating_zone": "Seating zone",
    "excluded_categories": "Left out", "products_per_category": "Products per category",
}


def _describe(key: str, value: Any, labels: Mapping[str, str]) -> str:
    if key in ("width", "height", "aisle_width"):
        text = f"{value} cells"
    elif key == "excluded_categories":
        text = ", ".join(labels.get(c, c) for c in value)
    elif key == "design_colors":
        text = ", ".join(f"{part} {color}" for part, color in value.items() if color)
    else:
        text = str(value).replace("_", " ")
    return f"{_LABELS.get(key, key)}: {text}"


def to_options(brief: _Brief, current: Mapping[str, Any], categories: Sequence[tuple[str, str]]) -> BriefReading:
    """The brief's options checked one by one against the current options; an option that does not fit is reported."""
    labels = dict(categories)
    by_name: dict[str, str] = {}
    for cid, label in categories:
        by_name.setdefault(cid.casefold(), cid)
        by_name.setdefault(label.casefold(), cid)
    warnings: list[str] = []
    wanted: dict[str, Any] = {}
    for key in ("style", "density", "aisle_width", "shelf_direction", "entrance", "gate_wall", "checkouts",
                "checkout_placement", "checkout_wall", "design_theme", "dining_tables", "seating_zone", "products_per_category"):
        value = getattr(brief, key)
        if value is not None:
            wanted[key] = value
    if brief.width is not None:
        wanted["width"] = brief.width
    if brief.depth is not None:
        wanted["height"] = brief.depth
    if brief.design_colors is not None:
        colors: dict[str, str] = {}
        for part, color in brief.design_colors.model_dump().items():
            if not color:
                continue
            if _HEX.fullmatch(color.strip()):
                colors[part] = color.strip().lower()
            else:
                warnings.append(f'The {part} color "{color}" is not a #rrggbb color; it was not applied.')
        if colors:
            wanted["design_colors"] = colors
    excluded: list[str] = []
    for asked in brief.excluded_categories:
        cid = resolve_listed(asked, by_name)
        if cid is None:
            warnings.append(f'No category "{asked}" in this format; nothing was left out for it.')
        elif cid not in excluded:
            excluded.append(cid)
    if excluded:
        wanted["excluded_categories"] = sorted(set(excluded) | set(current.get("excluded_categories") or []))
    current = {k: v for k, v in current.items() if k in LayoutOptions.model_fields}
    accepted: dict[str, Any] = {}
    for key, value in wanted.items():
        try:
            LayoutOptions.model_validate({**current, **accepted, key: value})
        except ValidationError as e:
            reason = e.errors()[0].get("msg", "not allowed") if e.errors() else "not allowed"
            warnings.append(f"{_describe(key, value, labels)} was not applied ({reason}).")
            continue
        accepted[key] = value
    return BriefReading(
        options=accepted, applied=[_describe(k, v, labels) for k, v in accepted.items()],
        not_expressible=[n.strip() for n in brief.not_expressible if n.strip()], warnings=warnings,
        rationale=brief.rationale.strip(),
    )


def _format(template: Mapping[str, Any], categories: Sequence[tuple[str, str]]) -> str:
    grid = template.get("grid") or ("?", "?")
    lines = [
        f"Format: {template.get('name', '')} ({template.get('store_type', '')}); {template.get('description', '')}",
        (f"Default size: {grid[0]} by {grid[1]} grid cells; default style {template.get('style', '')}; "
         f"default tills {template.get('checkouts', '')}; default dining tables {template.get('dining_tables', 0)}"),
        f"Categories: {', '.join(label for _, label in categories) or 'none'}",
    ]
    return "\n".join(lines)


async def read_brief(
    llm: StructuredLLM, brief: str, template: Mapping[str, Any], categories: Sequence[tuple[str, str]],
    current: Mapping[str, Any],
) -> BriefReading:
    """template: name, store_type, description, grid, style, checkouts, dining_tables; categories: (id, label)."""
    reading = await llm.generate_structured_async(
        _Brief, BRIEF_PROMPT, f"{_format(template, categories)}\n\nBrief: {brief.strip()}", max_retries=2, seed=0,
    )
    return to_options(reading, current, categories)
