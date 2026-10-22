"""3D photos of shelf faces shown above the chart (shelf_view "photo_chart"): keys, storage, the composite
view and the engine's use of it, with a scripted VLM."""

import asyncio
import io
import json
import random
from pathlib import Path

import pytest
from PIL import Image
from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face, TokenUsage, Weekday
from store_emulator.engine.perception import render_face
from store_emulator.engine.perception.shelf_photo import (
    face_key,
    item_ref,
    load_shelf_photo,
    photo_chart_view,
    save_shelf_photo,
    stocked_faces,
)
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import PHOTO_LINE, SYSTEM_PROMPT, glance_system_prompt

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


def _store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


def _rack() -> Rack:
    return Rack(
        id="r1", type=RackType.SHELF, shape=[[1, 1]], position=(3, 4), rack_name="Snacks",
        slots=[
            Slot(block=0, face=Face.S, level=3, items=[SlotItem(sku="a", name="Crunchy Chips 8oz", price=429),
                                                       SlotItem(sku="b", name="Cheese Puffs 8oz", price=399, promo="1+1")]),
            Slot(block=1, face=Face.S, level=2, items=[SlotItem(sku="c", name="Pretzel Twists 10oz", price=349)]),
        ],
    )


def _jpeg(size: tuple[int, int] = (640, 480), color: tuple[int, int, int] = (40, 90, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def test_face_key_follows_what_the_face_shows_not_where_the_rack_stands():
    rack = _rack()
    key = face_key(rack, Face.S, "USD")
    assert len(key) == 64 and key == face_key(rack, Face.S, "usd")
    moved = rack.model_copy(update={"position": (9, 9), "dwell_min": 5})
    assert face_key(moved, Face.S, "USD") == key
    repriced = rack.model_copy(deep=True)
    repriced.slots[0].items[0].price = 449
    assert face_key(repriced, Face.S, "USD") != key
    assert face_key(rack, Face.N, "USD") != key
    assert face_key(rack, Face.S, "KRW") != key
    assert stocked_faces(rack) == [Face.S]


def test_save_and_load_keep_boxes_inside_the_picture_and_reject_bad_input(tmp_path: Path):
    key = face_key(_rack(), Face.S, "USD")
    size = save_shelf_photo(tmp_path, key, _jpeg(), {"S:3:0:0": [(10, 20, 120, 200)], "S:2:1:0": [(600, 400, 900, 700)],
                                                    "S:3:0:1": [(5, 5, 6, 6)]})
    assert size == (640, 480)
    photo = load_shelf_photo(str(tmp_path), key)
    assert photo is not None and photo.image.size == (640, 480)
    assert photo.boxes["S:3:0:0"] == ((10, 20, 120, 200),)
    assert photo.boxes["S:2:1:0"] == ((600, 400, 640, 480),)   # clamped to the picture
    assert "S:3:0:1" not in photo.boxes                       # too small to place a tag
    assert load_shelf_photo(str(tmp_path), "0" * 64) is None
    with pytest.raises(ValueError):
        save_shelf_photo(tmp_path, "../escape", _jpeg(), {})
    with pytest.raises(ValueError):
        save_shelf_photo(tmp_path, key, b"not a picture", {})
    with pytest.raises(ValueError):
        save_shelf_photo(tmp_path, key, _jpeg((32, 32)), {})


def test_photo_chart_view_keeps_the_chart_marks_and_tags_the_photo():
    rack = _rack()
    chart = render_face(rack, Face.S, currency="USD", width=512, rng=random.Random(7))
    boxes = {item_ref(slot, k): ((40.0 + 200 * i, 100.0, 180.0 + 200 * i, 300.0),)
             for i, (slot, k) in enumerate((s, k) for s in rack.slots for k in range(len(s.items)))}
    from store_emulator.engine.perception.shelf_photo import ShelfPhoto
    photo = ShelfPhoto(image=Image.new("RGB", (640, 480), (40, 90, 160)), boxes=boxes)
    view = photo_chart_view(chart, photo)
    assert view.items == chart.items and view.rack is chart.rack
    img = Image.open(io.BytesIO(view.png))
    assert img.size == view.size and img.width == 512 and img.height > chart.size[1] + 380
    # A yellow tag sits where the first product's box ends (scaled 512/640), on the photo part.
    yellow = [img.getpixel((x, y)) for x in range(70, 130) for y in range(225, 250)]
    assert any(isinstance(p, tuple) and p[0] > 220 and p[1] > 190 and p[2] < 90 for p in yellow)


class _RecordingVLM:
    def __init__(self) -> None:
        self.systems: list[str] = []
        self.heights: list[int] = []

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        import base64
        self.systems.append(system_prompt)
        self.heights.append(Image.open(io.BytesIO(base64.b64decode(image_url.split(",", 1)[1]))).height)
        return response_model.model_validate({"product": "", "number": 1, "interest": 6, "reason": "bright pack"})

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=len(self.systems))


def _config(view: str, directory: str) -> SimulationConfig:
    cfg = SimulationConfig(engine_type=EngineType.VLM_GLANCE)
    vlm = cfg.engines.vlm_glance.model_copy(update={"glance_policy": "all", "max_glances": 3, "image_width": 384,
                                                    "plan_policy": "rule", "shelf_view": view,
                                                    "shelf_views_dir": directory})
    return cfg.model_copy(update={"engines": cfg.engines.model_copy(update={"vlm_glance": vlm})})


def _glances(view: str, directory: str) -> tuple[VLMGlanceEngine, _RecordingVLM]:
    store = _store()
    vlm = _RecordingVLM()
    engine = VLMGlanceEngine(llm=vlm, pathfinder=AStarPathFinder(), config=_config(view, directory))  # type: ignore[arg-type]
    personas = [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())][:8]
    for i, persona in enumerate(personas):
        context = PerCustomerContext(
            store=store, persona=persona, day=Weekday.MON, arrival_hour=12, concurrent_visitors_in_hour=3,
            cue=BehaviorCue(state="목마름", emotion="기분좋음"), behavior_patterns=BEHAVIOR_PATTERNS, seed=500 + i,
        )
        asyncio.run(engine.decide_actions(context))
    return engine, vlm


def test_engine_shows_the_photo_where_one_is_stored_and_the_chart_elsewhere(tmp_path: Path):
    store = _store()
    _, chart_vlm = _glances("chart", "")
    assert chart_vlm.systems and all(s == glance_system_prompt(store.type) for s in chart_vlm.systems)

    # Photograph every face but one.
    faces = [(rack, face) for rack in store.product_racks for face in stocked_faces(rack)]
    for rack, face in faces[1:]:
        save_shelf_photo(tmp_path, face_key(rack, face, store.currency or "USD"), _jpeg(), {})
    engine, vlm = _glances("photo_chart", str(tmp_path))
    records = engine.glance_log
    views = {r.view for r in records}
    assert "photo_chart" in views
    skipped = faces[0][0].rack_name
    assert all(r.view == "chart" for r in records if r.rack == skipped and r.face == faces[0][1].value)
    photo_prompt = glance_system_prompt(store.type, photo=True)
    assert PHOTO_LINE in photo_prompt and SYSTEM_PROMPT.splitlines()[1] not in photo_prompt
    assert sum(s == photo_prompt for s in vlm.systems) == sum(r.view == "photo_chart" for r in records)
    meta = engine.metadata()
    assert meta["shelf_view"] == "photo_chart" and meta["views"] == {
        v: sum(r.view == v for r in records) for v in views}
    # The same shoppers glance at the same faces either way: only what each glance shows changes.
    chart_engine, _ = _glances("chart", "")
    assert [(r.persona_id, r.rack, r.face) for r in chart_engine.glance_log] == [
        (r.persona_id, r.rack, r.face) for r in records]


def test_a_photo_of_an_older_layout_is_not_shown(tmp_path: Path):
    store = _store()
    rack = store.product_racks[0]
    face = stocked_faces(rack)[0]
    stale = rack.model_copy(deep=True)
    stale.slots[0].items[0].price += 10
    save_shelf_photo(tmp_path, face_key(stale, face, store.currency or "USD"), _jpeg(), {})
    engine, _ = _glances("photo_chart", str(tmp_path))
    assert all(r.view == "chart" for r in engine.glance_log)
