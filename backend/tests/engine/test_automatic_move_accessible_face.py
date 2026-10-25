"""An unspecified face should use a reachable side of the requested shelf."""

import asyncio
import json
from collections import Counter

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.rack import BlockFace, Rack, Slot, SlotItem
from store_emulator.engine.layout_edit import draft_layout_edit
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import design_experiment
from store_emulator.engine.marketing.variants import apply_changes
from store_emulator.engine.validation import list_blocked_faces
from tests.engine.test_layout_applied_changes import fixture


def layout(blocked, full=False, reverse=False):
    store, change = fixture("valid")
    target = store.racks[2]
    target.slots += [Slot(block=0, face="N", level=2,
        items=[SlotItem(sku=f"north{i}", name=f"North {i}", price=99) for i in range(4)]),
        Slot(block=0, face="S", level=3,
            items=[SlotItem(sku=f"south{i}", name=f"South {i}", price=99) for i in range(4)] if full else [])]
    if blocked == "locked":
        target.locked_faces = [BlockFace(block=0, face="N")]
    elif blocked == "wall":
        target.position = (5, 0)
    else:
        store.racks.append(Rack(id="blocker", type="shelf", shape=[[1]], position=(5, 2)))
    if reverse:
        target.slots.reverse()
    blocked_faces = {(b.rack_id, b.face) for b in list_blocked_faces(store)}
    assert ("target", "N") in blocked_faces and ("target", "S") not in blocked_faces
    return store, change


@pytest.mark.parametrize("kind", ["layout", "experiment"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("blocked", ["locked", "wall", "occupied"])
@pytest.mark.parametrize("full", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_automatic_moves_use_the_reachable_face_without_reasking_the_model(monkeypatch, tmp_path, kind, mode, blocked, full, reverse):
    store, change = layout(blocked, full, reverse)
    before = store.model_dump_json()
    contents = Counter(i.model_dump_json() for r in store.racks for s in r.slots for i in s.items)
    payload = {"name": "Move tea", **({"changes": [change]} if kind == "layout" else {
        "variants": [{"name": "Move tea", "changes": [change]}]})}
    calls = []
    async def asend(self, request, *args, **kwargs):
        calls.append(request)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "move-access", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model="openai/move-access", api_base="http://127.0.0.1:8081/v1", api_key="offline",
        structured_output=mode, cache_dir=str(tmp_path)))
    async def draft():
        if kind == "layout":
            return await draft_layout_edit(client, "Move Tea to Destination at eye level", store, "USD")
        return await design_experiment(client, "Test Tea at Destination eye level", store, "USD", [])
    async def exercise():
        result = await draft()
        changes = result.changes if kind == "layout" else result.variants[0].changes
        updated, applied, warnings = apply_changes(store, changes)
        assert len(applied) == 1 and not warnings and not result.warnings
        places = [(r.id, s.face, s.level) for r in updated.racks for s in r.slots for i in s.items if i.sku == "tea"]
        assert places == [("target", "S", 3)]
        assert Counter(i.model_dump_json() for r in updated.racks for s in r.slots for i in s.items) == contents
        blocked_faces = {(b.rack_id, b.block, b.face) for b in list_blocked_faces(updated)}
        assert all((r.id, s.block, s.face) not in blocked_faces for r in updated.racks for s in r.slots
            if any(i.sku == "tea" or full and i.sku == "south3" for i in s.items))
        assert await draft() == result and client.get_usage().cached_requests == 1 and len(calls) == 1
        assert store.model_dump_json() == before
    asyncio.run(exercise())


@pytest.mark.parametrize("blocked", ["locked", "wall", "occupied"])
@pytest.mark.parametrize("explicit", [False, True])
def test_explicit_blocked_faces_and_fully_blocked_shelves_still_warn(blocked, explicit):
    store, _ = layout(blocked)
    if not explicit:
        store.racks[2].locked_faces.append(BlockFace(block=0, face="S"))
    change = VariantChange(kind="move", sku="tea", rack_id="target", level=3, face="N" if explicit else None)
    updated, applied, warnings = apply_changes(store, [change])
    assert not applied and any("cannot reach" in warning for warning in warnings)
    assert updated.model_dump() == store.model_dump()
