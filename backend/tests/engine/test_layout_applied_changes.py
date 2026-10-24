"""Resolving names is insufficient: automatic drafts must apply a real operation."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import BlockFace, Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine import llm_client
from store_emulator.engine.layout_edit import draft_layout_edit
from store_emulator.engine.marketing.experiment_design import _Draft, design_experiment, to_design
from store_emulator.engine.marketing.variants import apply_changes


def fixture(case):
    target = Rack(id="target", rack_name="Destination", type="shelf", shape=[[1]], position=(5, 3), slots=[
        Slot(block=0, face="N", level=1, items=[SlotItem(sku="water", name="Water", price=99)])])
    source = Rack(id="source", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
        Slot(block=0, face="N", level=1, items=[SlotItem(sku="tea", name="Tea", price=199)])])
    change = {"kind": "move", "product": "Tea", "shelf": "Destination", "level": 3}
    if case in {"missing-category", "empty-category", "empty-shelf"}:
        target.slots = []
    if case == "missing-category":
        change = {"kind": "category_price", "category": "Imaginary", "percent": -10}
    elif case == "empty-category":
        change = {"kind": "category_price", "category": "Destination", "percent": -10}
    elif case == "locked":
        target.locked_faces = [BlockFace(block=0, face="N")]
    elif case == "outer-wall":
        target.position = (5, 0)
    elif case == "already-there":
        change.update(shelf="Drinks", level=1)
    store = Store(id="s", name="Store", type="convenience", grid_size=(8, 8), racks=[
        Rack(id="door", type="entrance", shape=[[1]], position=(0, 7)), source, target])
    return store, change


CASES = ["missing-category", "empty-category", "empty-shelf", "locked", "outer-wall", "already-there"]


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("kind", ["layout", "experiment"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("recovers", [False, True])
def test_model_corrects_edits_that_resolve_but_cannot_apply(monkeypatch, tmp_path, case, kind, mode, recovers):
    store, bad_change = fixture(case)
    before = store.model_dump_json()
    requests, retry_later = [], False
    original = llm_client.litellm.acompletion

    def payload(change):
        return {"name": "Draft", **({"changes": [change]} if kind == "layout" else {
            "variants": [{"name": "Variant", "changes": [change]}]})}

    good = {"kind": "promo", "product": "Tea", "promo": "NEW"}

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        change = good if retry_later or recovers and len(requests) > 1 else bad_change
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload(change))}}]})

    async def exercise():
        nonlocal retry_later
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/applied-edits", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def draft():
                if kind == "layout":
                    return await draft_layout_edit(client, "Change the layout", store, "USD")
                return await design_experiment(client, "Compare the changes", store, "USD", [])

            if not recovers:
                with pytest.raises(InstructorRetryException):
                    await draft()
                assert len(requests) == 2 and not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await draft()
            changes = result.changes if kind == "layout" else result.variants[0].changes
            edited, applied, warnings = apply_changes(store, changes)
            assert applied and not warnings
            assert edited.racks[1].slots[0].items[0].promo == "NEW"
            assert await draft() == result
            assert len(requests) == (2 if recovers else 3)
            assert "no change" in json.dumps(requests[1]["messages"]).lower()
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("same_variant", [False, True])
def test_keep_applied_variants_and_partial_edits_with_warnings(case, same_variant):
    store, bad = fixture(case)
    before = store.model_dump_json()
    good = {"kind": "promo", "product": "Tea", "promo": "NEW"}
    variants = ([{"name": "Mixed", "changes": [bad, good]}] if same_variant else
                [{"name": "Unusable", "changes": [bad]}, {"name": "Useful", "changes": [good]}])
    result = to_design(_Draft.model_validate({"name": "Test", "variants": variants}), store, "USD", [])
    assert len(result.variants) == 1
    assert result.warnings
    edited, applied, _ = apply_changes(store, result.variants[0].changes)
    assert applied and edited.racks[1].slots[0].items[0].promo == "NEW"
    assert store.model_dump_json() == before
