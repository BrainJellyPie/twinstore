"""Names longer than local grammar fields must resolve only to a unique target."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.layout_edit import draft_layout_edit
from store_emulator.engine.marketing.experiment_design import _Draft, design_experiment, to_design
from store_emulator.engine.marketing.variants import apply_changes
from tests.engine.test_layout_applied_changes import fixture


def named_fixture(target, character="x"):
    store, move = fixture("valid")
    limit = 120 if target == "product" else 80
    prefix = character * limit
    full = prefix + " full name"
    packages = []
    if target == "product":
        store.racks[1].slots[0].items[0].name = full
        change = {"kind": "price", "product": prefix, "price": 1.49}
    elif target == "shelf":
        store.racks[2].rack_name = full
        change = {**move, "shelf": prefix}
    else:
        packages = [(full, "new-pack")]
        change = {"kind": "package", "product": "Tea", "package": prefix}
    return store, change, packages, prefix


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind,target", [(kind, target) for kind in ["layout", "experiment"]
    for target in ["product", "shelf", "package"] if kind == "experiment" or target != "package"])
@pytest.mark.parametrize("character", ["X", "茶"])
def test_bounded_name_keeps_the_exact_edit_target_and_cache(monkeypatch, tmp_path, mode, kind, target, character):
    store, change, packages, _ = named_fixture(target, character)
    payload = {"name": "Draft", **({"changes": [change]} if kind == "layout" else {
        "variants": [{"name": "Variant", "changes": [change]}]})}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/bounded-edit-names", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            before = store.model_dump_json()

            async def draft():
                if kind == "layout":
                    return await draft_layout_edit(client, "Apply the requested edit", store, "USD")
                return await design_experiment(client, "Compare the requested edit", store, "USD", packages)

            result = await draft()
            operations = result.changes if kind == "layout" else result.variants[0].changes
            assert len(operations) == 1 and operations[0].sku == "tea"
            edited, applied, warnings = apply_changes(store, operations, package_uris={"new-pack": "new.png"})
            assert len(applied) == 1 and not warnings and not result.warnings
            tea = [(r.id, s.level, i) for r in edited.racks for s in r.slots for i in s.items if i.sku == "tea"]
            assert len(tea) == 1
            if target == "product":
                assert tea[0][2].price == 149
            elif target == "shelf":
                assert tea[0][:2] == ("target", 3)
            else:
                assert tea[0][2].image_url == "new.png" and result.engine == "vlm"
            assert await draft() == result and len(calls) == 1 and client.get_usage().cached_requests == 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("target", ["product", "shelf", "package"])
@pytest.mark.parametrize("collision", ["another-long", "exact-boundary", "same-id", "short-prefix"])
def test_bounded_names_never_choose_between_distinct_targets(target, collision):
    store, change, packages, prefix = named_fixture(target)
    if collision == "short-prefix":
        change[target] = prefix[:-1]
    else:
        second = prefix if collision == "exact-boundary" else prefix + " different suffix"
        if target == "product":
            store.racks[1].slots[0].items.append(SlotItem(sku="tea" if collision == "same-id" else "other", name=second, price=199))
        elif target == "shelf":
            duplicate = store.racks[2].model_copy(deep=True, update={"id": "target" if collision == "same-id" else "other",
                "rack_name": second, "position": (5, 5)})
            store.racks.append(duplicate)
        else:
            packages.append((second, "new-pack" if collision == "same-id" else "other-pack"))
    draft = _Draft.model_validate({"name": "Draft", "variants": [{"name": "Variant", "changes": [change]}]})
    if collision == "same-id":
        result = to_design(draft, store, "USD", packages)
        assert result.variants[0].changes[0].sku == "tea"
    else:
        with pytest.raises(ValueError, match="no change"):
            to_design(draft, store, "USD", packages)
