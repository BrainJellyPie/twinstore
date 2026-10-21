"""Floor plan import: a sketched plan read without a model, then turned into a valid stocked layout."""

import asyncio
import random

import pytest
from PIL import Image, ImageDraw, ImageFilter
from pydantic import BaseModel

from store_emulator.domain.floorplan import FloorPlanReading, PlanFixture
from store_emulator.domain.rack import RackType
from store_emulator.engine.floorplan import classic_read, plan_to_store, vlm_read
from store_emulator.engine.floorplan.build import grid_for
from store_emulator.engine.validation import validate


def sketch(seed: int = 0, *, outlined_gondolas: bool = True) -> Image.Image:
    """A pen sketch of a small store: walls with a door gap at the bottom left, a fridge row on the
    back wall, a wall shelf on the right, two free-standing gondolas and a counter by the door."""
    rng = random.Random(seed)
    img = Image.new("RGB", (1000, 760), (247, 245, 238))
    d = ImageDraw.Draw(img)
    j = lambda v: v + rng.uniform(-3, 3)  # noqa: E731 — hand jitter
    ink = (30, 32, 40)
    x1, y1, x2, y2 = 80, 60, 920, 700
    lw = 7
    d.line([(j(x1), j(y1)), (j(x2), j(y1))], fill=ink, width=lw)
    d.line([(j(x2), j(y1)), (j(x2), j(y2))], fill=ink, width=lw)
    d.line([(j(x1), j(y1)), (j(x1), j(y2))], fill=ink, width=lw)
    d.line([(j(x1), j(y2)), (j(200), j(y2))], fill=ink, width=lw)   # door gap 200–330 on the bottom wall
    d.line([(j(330), j(y2)), (j(x2), j(y2))], fill=ink, width=lw)
    d.rectangle((150, 85, 780, 135), fill=ink)                        # fridges along the back wall
    d.rectangle((860, 220, 895, 560), fill=ink)                       # wall shelf on the right
    for gx in (300, 560):
        box = (gx, 260, gx + 170, 320)
        if outlined_gondolas:
            d.rectangle(box, outline=ink, width=5)
        else:
            d.rectangle(box, fill=ink)
    d.rectangle((360, 620, 430, 670), fill=ink)                       # counter by the door
    return img.filter(ImageFilter.GaussianBlur(0.8))


def test_classic_reader_finds_fixtures_and_door() -> None:
    reading = classic_read(sketch())
    kinds = sorted(f.kind for f in reading.fixtures)
    assert kinds.count("gondola") == 2 and "fridge" in kinds and "shelf" in kinds
    assert "entrance" in kinds and "counter" in kinds
    door = next(f for f in reading.fixtures if f.kind == "entrance")
    assert door.y1 > 0.9 and door.x2 < 0.4  # bottom wall, left part
    assert reading.width_m > reading.depth_m > 0 and reading.reader == "classic"


@pytest.mark.parametrize("outlined", [True, False])
def test_plan_becomes_a_valid_stocked_store(outlined: bool) -> None:
    reading = classic_read(sketch(seed=3, outlined_gondolas=outlined))
    store, notes = plan_to_store(reading, currency="USD", name="Sketch")
    assert not [i for i in validate(store) if i.severity == "error"], notes
    w, h = store.grid_size
    assert 8 <= w <= 16 and 8 <= h <= 16 and w > h
    fridges = [r for r in store.racks if r.type == RackType.FRIDGE]
    shelves = [r for r in store.racks if r.type == RackType.SHELF]
    assert fridges and all(r.position[1] <= 1 for r in fridges)  # on the back wall
    assert any(len({s.face for s in r.slots}) == 2 for r in shelves)  # gondolas shopped from both sides
    assert all(r.slots for r in fridges + shelves)
    entrance = next(r for r in store.racks if r.type == RackType.ENTRANCE)
    assert entrance.position[1] == h - 1
    assert any(r.type == RackType.COUNTER for r in store.racks)


def test_grid_keeps_proportions() -> None:
    assert grid_for(FloorPlanReading(width_m=30, depth_m=15)) == (16, 8)
    assert grid_for(FloorPlanReading(width_m=12, depth_m=10)) == (10, 8)


def test_labels_choose_the_category() -> None:
    reading = FloorPlanReading(width_m=12, depth_m=10, fixtures=[
        PlanFixture(kind="gondola", x1=0.3, y1=0.4, x2=0.7, y2=0.5, label="snacks"),
        PlanFixture(kind="fridge", x1=0.1, y1=0.0, x2=0.6, y2=0.08, label="beer"),
    ])
    store, _ = plan_to_store(reading)
    descs = {r.rack_desc for r in store.racks if r.slots}
    assert "chips" in descs and "beer_alcohol" in descs


class _PlanVLM:
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        return response_model.model_validate({
            "outline": [100, 100, 900, 900], "width_m": 15, "depth_m": 15,
            "fixtures": [{"kind": "fridge", "box": [150, 110, 850, 160], "label": "drinks"},
                         {"kind": "gondola", "box": [300, 450, 700, 520], "label": ""},
                         {"kind": "entrance", "box": [120, 880, 200, 900], "label": ""}],
        })


def test_vlm_reader_normalizes_boxes_to_the_outline() -> None:
    reading = asyncio.run(vlm_read(_PlanVLM(), sketch(), model="fake"))
    fridge = next(f for f in reading.fixtures if f.kind == "fridge")
    assert fridge.x1 == pytest.approx(0.0625) and fridge.y2 == pytest.approx(0.075)
    assert reading.width_m == 15 and reading.reader == "fake"
    store, _ = plan_to_store(reading)
    assert store.grid_size == (12, 12)
