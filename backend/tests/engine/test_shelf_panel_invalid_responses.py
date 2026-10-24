"""Invalid model choices must not manufacture agreement or merchandising lift."""

import asyncio

import pytest
from PIL import Image
from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.shelf_lab import PhotoEdit, Sim2RealCondition
from store_emulator.domain.types import Face
from store_emulator.engine.perception import render_face
from store_emulator.engine.shelf_lab import levers
from store_emulator.engine.shelf_lab.sim2real import TwinViews, glance_panel, summarize
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance

CONDITIONS: list[Sim2RealCondition] = ["render", "photo", "photo_raw"]


class ScriptedVLM:
    def __init__(self, replies: list[ShelfGlance | Exception]):
        self.replies = iter(replies)

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return response_model.model_validate(reply.model_dump())


@pytest.fixture
def views():
    rack = Rack(id="shelf", type="shelf", position=(1, 1), shape=[[1]], slots=[
        Slot(block=0, face=Face.S, level=level, items=[SlotItem(sku=sku, name=name, price=100)])
        for level, sku, name in [(1, "water", "Water"), (2, "tea1", "Tea"), (3, "tea2", "Tea")]
    ])
    view = render_face(rack, Face.S, width=256)
    return TwinViews(rack, Face.S, {c: view for c in CONDITIONS}, {m.item.sku: m.item.name for m in view.items})


def panel(views, replies, conditions=CONDITIONS):
    people = [Persona(id=f"p{i}", identity="shopper", age_group="30s", gender="Female",
                      description="", intent="", purpose="") for i in range(len(replies) // len(conditions))]
    progress = []
    answers = asyncio.run(glance_panel(
        ScriptedVLM(replies), views, people, conditions=conditions, cue_sampler=lambda rng: BehaviorCue(),
        patterns=BEHAVIOR_PATTERNS, on_progress=lambda done, total: progress.append((done, total)),
    ))
    assert progress[-1] == (len(replies), len(replies))
    return answers


@pytest.mark.parametrize("reply", [
    ShelfGlance(product="Unicorn battery", interest=10),
    ShelfGlance(number=10000, interest=10),
    ShelfGlance(product="Tea", interest=10),
    ShelfGlance(product="Tea", number=10000, interest=10),
])
def test_unresolvable_replies_cannot_report_perfect_agreement(views, reply):
    answers = panel(views, [reply] * 9)
    # Contextual response validation now rejects these before they can be cached.
    assert all(a.resolved_by == "error" and a.error for a in answers)
    stats, agreement = summarize(answers, CONDITIONS)
    assert all(s.answers == 0 and s.errors == 3 and s.none_rate == 0 and s.mean_interest == 0 for s in stats)
    assert agreement == []


@pytest.mark.parametrize("blank", ["", " ", "\t\n"])
@pytest.mark.parametrize("number", [1, 10000])
def test_raw_photo_number_only_is_not_an_explicit_no_pick(views, blank, number):
    answers = panel(views, [ShelfGlance(product=blank, number=number, interest=9)], ["photo_raw"])
    assert answers[0].resolved_by == "error" and answers[0].error


@pytest.mark.parametrize("reply,sku", [(ShelfGlance(), ""), (ShelfGlance(product="Water", interest=7), "water")])
def test_valid_no_pick_and_named_pick_remain_comparable(views, reply, sku):
    answers = panel(views, [reply] * 9)
    assert all(not a.error and a.sku == sku for a in answers)
    stats, agreement = summarize(answers, CONDITIONS)
    assert all(s.answers == 3 and s.errors == 0 and s.none_rate == (0 if sku else 1) for s in stats)
    assert all(a.pairs == 3 and a.same_pick == 1 for a in agreement)


def test_number_can_disambiguate_tagged_photos_but_not_raw_photos(views):
    number = next(m.mark for m in views.views["render"].items if m.item.sku == "tea2")
    answers = panel(views, [ShelfGlance(product="Tea", number=number, interest=8)] * 3)
    assert [a.sku for a in answers] == ["tea2", "tea2", ""]
    assert [bool(a.error) for a in answers] == [False, False, True]
    _, agreement = summarize(answers, CONDITIONS)
    assert [(a.condition, a.pairs, a.same_pick) for a in agreement] == [("photo", 1, 1)]


@pytest.mark.parametrize("bad_side", [0, 1, 2])
@pytest.mark.parametrize("failure", [ShelfGlance(product="Unicorn battery", interest=10), RuntimeError("offline failure")])
def test_only_complete_valid_pairs_contribute_to_statistics(views, bad_side, failure):
    # One valid pick, one explicit no-pick, and one shopper with a failed condition.
    replies = [ShelfGlance(product="Water", interest=6)] * 3 + [ShelfGlance()] * 3
    tail = [ShelfGlance(product="Water", interest=6)] * 3
    tail[bad_side] = failure
    answers = panel(views, replies + tail)
    stats, agreement = summarize(answers, CONDITIONS)
    assert stats[bad_side].answers == 2 and stats[bad_side].errors == 1
    assert stats[bad_side].none_rate == 0.5 and stats[bad_side].mean_interest == 3
    for result in agreement:
        expected = 2 if bad_side in (0, CONDITIONS.index(result.condition)) else 3
        assert result.pairs == expected and result.same_pick == 1


@pytest.mark.parametrize("failed_sides", [(0,), (1,), (0, 1)])
def test_merchandising_comparisons_exclude_unresolvable_pairs(views, monkeypatch, failed_sides):
    monkeypatch.setattr(levers, "build_views", lambda *args, **kwargs: views)
    capture = CaptureResult(image_size=(16, 16), items=[CaptureItem(
        id="i1", band=0, level=1, order=0, sku="water", name="Water", price=100, labeled=True,
    )])
    person = Persona(id="shopper", identity="shopper", age_group="30s", gender="Female",
                     description="", intent="", purpose="")
    replies = [ShelfGlance(product="Unicorn battery" if i in failed_sides else "Water", interest=9)
               for i in range(2)]
    with Image.new("RGB", (16, 16), "white") as photo:
        cf = levers.Counterfactual("cf", "price", PhotoEdit(kind="price", item_id="i1", price=90),
                                  photo, capture, photo, capture)
        result = asyncio.run(levers.run_lever(ScriptedVLM(replies), cf, [person],
                             cue_sampler=lambda rng: BehaviorCue(), patterns=BEHAVIOR_PATTERNS))
    assert result.personas == 0 and result.errors == 1
    assert result.picked_before == result.picked_after == result.changed_pick == 0
