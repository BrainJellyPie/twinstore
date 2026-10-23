"""Invalid shelf answers cannot become valid refusals or alter paired choice shares."""

import asyncio
from dataclasses import replace

import pytest

from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, RackType, Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.engine.marketing import shelf_test
from store_emulator.engine.perception.shelf_render import MarkedItem, ShelfView


def person(identifier="p"):
    return Persona(id=identifier, identity="Visitor", age_group="20s", gender="Female", description="",
                   intent="", purpose="snack")


@pytest.fixture
def shelf(monkeypatch):
    rack = Rack(id="rack", type=RackType.SHELF, shape=[[1]], position=(2, 2), slots=[
        Slot(block=0, face=Face.N, level=2, items=[SlotItem(sku="A", name="Apple", price=100),
                                                  SlotItem(sku="B", name="Banana", price=200)])
    ])
    view = ShelfView(rack=rack, face=Face.N, items=tuple(
        MarkedItem(mark=i + 1, slot=rack.slots[0], item=item) for i, item in enumerate(rack.slots[0].items)
    ), png=b"fake-image", size=(900, 500))
    monkeypatch.setattr(shelf_test, "render_arm", lambda *args: view)
    return rack, view


class Answering:
    def __init__(self, pick=0, noticed=()):
        self.pick, self.noticed = pick, list(noticed)

    async def generate_structured_with_image_async(self, schema, *args, **kwargs):
        return schema.model_validate({"pick": self.pick, "noticed": self.noticed, "why": "My choice"})


@pytest.mark.parametrize("pick,noticed", [(3, []), (999999, [1]), (1, [3]), (0, [0]), (2, [-1]),
                                          (1, [1, 2, 900]), (0, [999999])])
def test_nonexistent_badges_are_failures_not_valid_declines(shelf, pick, noticed):
    rack, _ = shelf
    choices = asyncio.run(shelf_test.shelf_panel(Answering(pick, noticed), [person()], rack, rack, Face.N))
    assert all(choice.error and not choice.pick_sku and not choice.noticed for choice in choices)
    assert shelf_test.compare_shelves(choices, "A") == []
    assert shelf_test.pick_shares(choices, {}) == []


@pytest.mark.parametrize("pick,noticed,sku,seen", [(0, [], "", []), (0, [2, 1], "", ["B", "A"]),
                                                   (1, [], "A", []), (2, [2, 2, 1], "B", ["B", "A"])])
def test_real_badges_and_explicit_refusals_remain_valid(shelf, pick, noticed, sku, seen):
    rack, _ = shelf
    choices = asyncio.run(shelf_test.shelf_panel(Answering(pick, noticed), [person()], rack, rack, Face.N))
    assert all(not choice.error and choice.pick_sku == sku and choice.noticed == seen for choice in choices)


@pytest.mark.parametrize("pick,noticed,valid", [(0, [], True), (1, [], False), (0, [1], False)])
def test_empty_changed_face_only_accepts_a_refusal(shelf, monkeypatch, pick, noticed, valid):
    rack, view = shelf
    monkeypatch.setattr(shelf_test, "render_arm", lambda *args: replace(view, items=()))
    choices = asyncio.run(shelf_test.shelf_panel(Answering(pick, noticed), [person()], rack, rack, Face.N))
    assert all(bool(choice.error) is not valid for choice in choices)


def test_each_arm_validates_its_own_visible_numbers(shelf, monkeypatch):
    rack, view = shelf
    changed = rack.model_copy(update={"id": "changed"})
    monkeypatch.setattr(shelf_test, "render_arm",
                        lambda r, *args: view if r.id == rack.id else replace(view, items=view.items[:1]))
    choices = asyncio.run(shelf_test.shelf_panel(Answering(2), [person()], rack, changed, Face.N))
    assert not choices[0].error and choices[0].pick_sku == "B"
    assert choices[1].error
    assert shelf_test.compare_shelves(choices, "B") == []


@pytest.mark.parametrize("concurrency", [1, 3, 6])
def test_queued_respondents_do_not_render_images_before_their_slot(shelf, monkeypatch, concurrency):
    rack, view = shelf
    rendered = []

    def render(*args):
        rendered.append(1)
        return view

    monkeypatch.setattr(shelf_test, "render_arm", render)

    async def exercise():
        ready, release = asyncio.Event(), asyncio.Event()

        class Waiting(Answering):
            calls = 0

            async def generate_structured_with_image_async(self, schema, *args, **kwargs):
                self.calls += 1
                if self.calls == concurrency:
                    ready.set()
                await release.wait()
                return await super().generate_structured_with_image_async(schema, *args, **kwargs)

        task = asyncio.create_task(shelf_test.shelf_panel(Waiting(1), [person(f"p{i}") for i in range(40)],
                                    rack, rack, Face.N, max_concurrent=concurrency))
        try:
            await asyncio.wait_for(ready.wait(), 2)
            await asyncio.sleep(0)
            assert len(rendered) == concurrency
        finally:
            release.set()
            result = await task
        assert len(result) == 80 and all(not choice.error for choice in result)

    asyncio.run(exercise())
