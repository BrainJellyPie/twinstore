"""Shelf rendering and the vision-language shopper engine, with a scripted fake VLM (no server)."""

import asyncio
import io
import json
import random
from pathlib import Path

from PIL import Image
from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, TokenUsage, Weekday
from store_emulator.engine.perception import render_face
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import (
    ShelfGlance,
    resolve,
)

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


def _store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


def _personas() -> list[Persona]:
    return [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]


class _ScriptedVLM:
    """Answers every glance with the first (or a named) product it was shown."""

    def __init__(self, answer: str = "first", interest: int = 10, fail: bool = False) -> None:
        self.answer, self.interest, self.fail = answer, interest, fail
        self.calls: list[tuple[str, str, int | None]] = []

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        self.calls.append((user_prompt, image_url[:40], seed))
        if self.fail:
            raise TimeoutError("vlm server timed out")
        assert image_url.startswith("data:image/png;base64,")
        if self.answer == "nothing":
            return response_model.model_validate({"product": "", "number": 0, "interest": 0, "reason": ""})
        if self.answer == "garbage":
            return response_model.model_validate({"product": "Unicorn Milk", "number": 99, "interest": 9, "reason": ""})
        return response_model.model_validate({"product": "", "number": 1, "interest": self.interest, "reason": "looks tasty"})

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=len(self.calls))


def _config(policy: str = "all", order: str = "shuffle") -> SimulationConfig:
    cfg = SimulationConfig(engine_type=EngineType.VLM_GLANCE)
    # Glance-only behavior: the rule planner decides the planned purchases (VLM planning: test_vlm_plan.py).
    vlm = cfg.engines.vlm_glance.model_copy(update={"glance_policy": policy, "max_glances": 3, "image_width": 384,
                                                    "plan_policy": "rule", "glance_order": order})
    return cfg.model_copy(update={"engines": cfg.engines.model_copy(update={"vlm_glance": vlm})})


def _context(store: Store, persona: Persona, seed: int) -> PerCustomerContext:
    return PerCustomerContext(
        store=store, persona=persona, day=Weekday.MON, arrival_hour=12, concurrent_visitors_in_hour=3,
        cue=BehaviorCue(state="목마름", emotion="기분좋음"), behavior_patterns=BEHAVIOR_PATTERNS, seed=seed,
    )


def test_render_face_marks_every_item_once_and_is_deterministic():
    rack = _store().product_racks[0]
    face = rack.slots[0].face
    a = render_face(rack, face, rng=random.Random(3))
    b = render_face(rack, face, rng=random.Random(3))
    n = sum(len(s.items) for s in rack.slots if s.face == face)
    assert sorted(m.mark for m in a.items) == list(range(1, n + 1))
    assert a.png == b.png
    assert [m.item.sku for m in a.items] == [m.item.sku for m in b.items]
    img = Image.open(io.BytesIO(a.png))
    assert img.size == a.size and a.size[0] == 768
    # Without an rng the numbering is reading order: the top level comes first.
    plain = render_face(rack, face)
    assert plain.by_mark(1) is not None and plain.by_mark(1).slot.level == 4  # type: ignore[union-attr]


def test_render_face_handles_korean_names_promos_and_krw():
    rack = Rack(
        id="r1", type=RackType.SHELF, shape=[[1]], position=(1, 1), rack_name="과자",
        slots=[Slot(block=0, face=Face.S, level=3, items=[
            SlotItem(sku="k1", name="새우깡 오리지널 90g", price=1500, promo="1+1"),
            SlotItem(sku="k2", name="포카칩 오리지널맛아주아주긴이름의과자제품", price=2000),
        ])],
    )
    view = render_face(rack, Face.S, currency="KRW", width=512)
    assert len(view.items) == 2 and view.size[0] == 512
    assert view.data_url().startswith("data:image/png;base64,")


def test_resolve_prefers_the_printed_name_and_falls_back_to_the_number():
    rack = _store().product_racks[0]
    view = render_face(rack, rack.slots[0].face, rng=random.Random(5))
    target = view.items[4]
    other = view.items[9]
    hit, how = resolve(view, ShelfGlance(product=target.item.name, number=other.mark, interest=7))
    assert how == "name" and hit is not None and hit.item.sku == target.item.sku
    hit, how = resolve(view, ShelfGlance(product="", number=other.mark))
    assert how == "number" and hit is not None and hit.item.sku == other.item.sku
    assert resolve(view, ShelfGlance())[1] == "none"
    assert resolve(view, ShelfGlance(product="Unicorn Milk", number=99))[1] == "invalid"


def _run(vlm: _ScriptedVLM, policy: str = "all", n: int = 16,
         order: str = "shuffle") -> tuple[VLMGlanceEngine, list[tuple[Persona, list[Action], list[str]]]]:
    store = _store()
    engine = VLMGlanceEngine(llm=vlm, pathfinder=AStarPathFinder(), config=_config(policy, order))  # type: ignore[arg-type]
    out: list[tuple[Persona, list[Action], list[str]]] = []
    for i, persona in enumerate(_personas()[:n]):
        decision = asyncio.run(engine.decide_actions(_context(store, persona, seed=1000 + i)))
        out.append((persona, [a.action for a in decision.actions if a.action],
                    [a.origin for a in decision.actions if a.action == Action.BUY]))
    return engine, out


def test_engine_turns_vlm_picks_into_impulse_buys():
    vlm = _ScriptedVLM(answer="first", interest=10)
    engine, results = _run(vlm)
    assert vlm.calls, "the VLM must be asked about at least one shelf"
    assert all(seed is not None for _, _, seed in vlm.calls)
    assert any("impulse" in origins for _, _, origins in results)
    meta = engine.metadata()
    assert meta["glances"] == len(vlm.calls)
    assert meta["outcomes"].get("buy", 0) > 0  # type: ignore[union-attr]
    assert {r["resolved_by"] for r in meta["records"]} <= {"number", "name", "none", "invalid"}  # type: ignore[union-attr]
    assert meta["mean_interest"] == 10


def test_interest_zero_never_buys_and_buy_scale_controls_the_rate():
    _, results = _run(_ScriptedVLM(interest=0))
    assert all("impulse" not in origins for _, _, origins in results)
    low, _ = _run(_ScriptedVLM(interest=10), n=24)
    cfg_store = low.metadata()
    assert cfg_store["buy_scale"] == 0.5


def test_nothing_noticed_means_no_impulse_and_failures_do_not_fail_customers():
    for vlm in (_ScriptedVLM(answer="nothing"), _ScriptedVLM(answer="garbage"), _ScriptedVLM(fail=True)):
        engine, results = _run(vlm, n=8)
        assert all("impulse" not in origins for _, _, origins in results)
        assert all(actions[0] == Action.ENTER and actions[-1] == Action.EXIT for _, actions, _ in results)
        meta = engine.metadata()
        if vlm.fail:
            assert meta["errors"] == meta["glances"] > 0
        if vlm.answer == "garbage":
            assert meta["resolved_by"] == {"invalid": meta["glances"]}


def test_gated_policy_asks_less_often_and_is_reproducible():
    every, _ = _run(_ScriptedVLM(), policy="all")
    gated_a, res_a = _run(_ScriptedVLM(), policy="gated")
    _, res_b = _run(_ScriptedVLM(), policy="gated")
    assert 0 < gated_a.metadata()["glances"] < every.metadata()["glances"]  # type: ignore[operator]
    assert res_a == res_b


def test_glances_spread_over_the_equally_seen_faces_of_each_route():
    """By rack id, every shopper's glances go to the same first racks; shuffled per shopper, they spread out."""
    assert SimulationConfig().engines.vlm_glance.glance_order == "shuffle"
    by_rack, _ = _run(_ScriptedVLM(answer="nothing"), n=24, order="rack")
    shuffled, _ = _run(_ScriptedVLM(answer="nothing"), n=24, order="shuffle")
    again, _ = _run(_ScriptedVLM(answer="nothing"), n=24, order="shuffle")

    def faces(engine: VLMGlanceEngine) -> list[tuple[str, str, str]]:
        return [(r["persona_id"], r["rack"], r["face"]) for r in engine.metadata()["records"]]  # type: ignore[index, union-attr]

    assert len({(r, f) for _, r, f in faces(shuffled)}) > len({(r, f) for _, r, f in faces(by_rack)})
    assert faces(shuffled) == faces(again)  # the draw is seeded per shopper, so runs repeat exactly


def test_vlm_receives_product_pixels_in_its_numbered_grid():
    import base64
    class PhotoVLM(_ScriptedVLM):
        def __init__(self):
            super().__init__()
            self.images = []
        async def generate_structured_with_image_async(self, response_model, system_prompt, user_prompt, image_url, **kwargs):
            self.images.append(Image.open(io.BytesIO(base64.b64decode(image_url.split(',', 1)[1]))).convert('RGB'))
            assert 'photo when available' in system_prompt
            return await super().generate_structured_with_image_async(response_model, system_prompt, user_prompt, image_url, **kwargs)
    store = _store()
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                item.image_url = '/project-photo.png'
    photo = Image.new('RGBA', (70, 100), (17, 203, 171, 255))
    requested = []
    def loader(item):
        requested.append(item.sku)
        return photo if item.image_url == '/project-photo.png' else None
    vlm = PhotoVLM()
    engine = VLMGlanceEngine(llm=vlm, pathfinder=AStarPathFinder(), config=_config(), image_loader=loader)
    for i, persona in enumerate(_personas()[:8]):
        asyncio.run(engine.decide_actions(_context(store, persona, seed=1000 + i)))
        if vlm.images:
            break
    assert vlm.images and requested
    assert all(sum(p == (17, 203, 171) for p in image.get_flattened_data()) > 100 for image in vlm.images)
    skus = {item.sku for rack in store.racks for slot in rack.slots for item in slot.items}
    assert all(r.resolved_sku in skus for r in engine.glance_log if r.resolved_sku)
