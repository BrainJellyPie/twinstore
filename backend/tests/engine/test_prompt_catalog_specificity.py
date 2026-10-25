"""A named product must not disappear behind a full catalog sharing one generic word."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine import hypotheses, llm_client, scenario_writer
from store_emulator.engine.layout_edit import apply_layout_edit, draft_layout_edit
from store_emulator.engine.marketing import conjoint_design, experiment_design, shelf_test_design, survey_design
from store_emulator.engine.marketing.variants import apply_changes
from store_emulator.engine.prompting import relevant_first
from store_emulator.engine.scenario import apply_to_store


def crowded_store(common, target):
    items = [SlotItem(sku=f"common-{i}", name=f"Everyday {common} {i}", price=100) for i in range(200)]
    items.append(SlotItem(sku="requested", name=target, price=100))
    rack = Rack(id="r1", type="shelf", shape=[[1] * 51], position=(1, 3), rack_name="Drinks", slots=[
        Slot(block=offset // 4, face="N", items=items[offset:offset + 4]) for offset in range(0, len(items), 4)])
    return Store(id="store", name="Large catalog", type="supermarket", grid_size=(64, 8), racks=[rack])


@pytest.mark.parametrize("common,target,query", [
    ("tea", "Saffron tea", "Discount Saffron tea by 20 percent"),
    ("teas", "Saffron tea", "Discount Saffron teas by 20 percent"),
    ("차음료", "제주유자 차음료", "제주유자 차음료를 20% 할인"),
    ("thé", "Thé safran", "Réduire le prix du THÉ SAFRAN de 20 pour cent"),
])
@pytest.mark.parametrize("kind", ["scenario", "experiment", "shelf", "conjoint", "survey", "hypotheses"])
def test_each_bounded_listing_keeps_the_more_specific_requested_product(common, target, query, kind):
    store = crowded_store(common, target)
    items = [item for slot in store.racks[0].slots for item in slot.items]
    if kind == "scenario":
        listing = scenario_writer._store_text(store, query)
    elif kind == "experiment":
        listing = experiment_design._listing(store, "USD", [], query)
    elif kind == "shelf":
        listing = shelf_test_design._listing(store, "USD", [], query)
    elif kind == "conjoint":
        listing = conjoint_design._shelf_text([(i.name, i.price) for i in items], "USD", query)
    elif kind == "survey":
        listing = survey_design._listing([(i.name, "Brand", "Pack") for i in items], query)
    else:
        listing = hypotheses._layout(store, query)
    assert target in listing
    assert listing.index(target) < listing.index(items[0].name)
    assert items[-2].name not in listing  # The catalog is still bounded.


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["scenario", "layout", "experiment", "shelf"])
@pytest.mark.parametrize("plural", [False, True])
def test_http_named_discount_reaches_only_its_product(monkeypatch, tmp_path, mode, kind, plural):
    target = "Saffron tea"
    query = "Discount Saffron teas by 20 percent" if plural else "Discount Saffron tea by 20 percent"
    store = crowded_store("teas" if plural else "tea", target)
    before = store.model_dump()
    change = {"kind": "discount", "product": target, "percent": -20}
    payload = ({"name": "Sale", "promotions": [{"kind": "discount", "target": target, "discount_pct": 20}]}
               if kind == "scenario" else {"name": "Sale", "changes": [change]} if kind == "layout" else
               {"name": "Sale", "variants": [{"name": "Sale", "changes": [change]}], "focus_products": [target]}
               if kind == "experiment" else {"name": "Sale", "product": target, "price": 0.80})
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        user = next(message["content"] for message in body["messages"] if message["role"] == "user")
        assert target in user.split("\n\n", 1)[0], "Requested product is absent from the supplied catalog"
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/catalog-specificity", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                if kind == "scenario":
                    result = await scenario_writer.describe_scenario(client, query, store)
                    edited, _ = apply_to_store(store, result.scenario)
                elif kind == "layout":
                    result = await draft_layout_edit(client, query, store, "USD")
                    edited, applied, warnings = apply_layout_edit(store, result.changes, "USD")
                    assert applied and not warnings and not result.warnings
                else:
                    if kind == "experiment":
                        result = await experiment_design.design_experiment(client, query, store, "USD", [])
                        changes = result.variants[0].changes
                        assert result.focus_skus == ["requested"]
                    else:
                        result = await shelf_test_design.design_shelf_test(client, query, store, "USD", [])
                        changes = result.changes
                        assert result.target_sku == "requested"
                    edited, applied, warnings = apply_changes(store, changes)
                    assert applied and not warnings and not result.warnings
                prices = {i.sku: i.price for r in edited.racks for s in r.slots for i in s.items}
                assert prices == {**{f"common-{i}": 100 for i in range(200)}, "requested": 80}
                assert store.model_dump() == before
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("limit", [1, 4, 80, 120, 150, 200])
def test_equal_relevance_stays_stable_and_limit_is_retained(limit):
    entries = [("Tea", f"Tea {index}", index) for index in range(201)]
    assert relevant_first(entries, "tea", limit) == list(range(limit))


def test_plural_expansion_is_not_counted_as_a_second_independent_match():
    entries = [("", "Teas", "generic"), ("", "Saffron tea", "specific")]
    assert relevant_first(entries, "Saffron teas", 1) == ["specific"]
