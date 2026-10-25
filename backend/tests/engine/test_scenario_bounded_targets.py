"""A truncated promotion target must not expand through broad keyword matching."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.scenario import apply_to_store
from store_emulator.engine.scenario_writer import ScenarioDraft, describe_scenario, to_scenario
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("language", ["en", "ko"])
@pytest.mark.parametrize("target_kind", ["product", "shelf"])
@pytest.mark.parametrize("collision", ["none", "long", "exact_limit"])
@pytest.mark.parametrize("promotion", ["discount", "1+1"])
def test_bounded_target_recovers_only_unique_names_before_prices_change(monkeypatch, tmp_path, mode, language, target_kind, collision, promotion):
    store = target_store()
    word = "Premium " if language == "en" else "프리미엄 "
    prefix = (word + ("Special Cola selection " if language == "en" else "특별 콜라 선물 상품 ") * 20)[:80]
    full = prefix + " original 500 ml"
    if target_kind == "product":
        store.racks[0].slots[0].items[0].name = full
        store.racks[1].slots[0].items[0].name = word + "other product"
        expected = {"s-cola"}
        if collision != "none":
            store.racks[0].slots[0].items[1].name = prefix + (" another size" if collision == "long" else "")
    else:
        store.racks[0].rack_name = full
        store.racks[1].rack_name = word + "other shelf"
        expected = {"s-cola", "s-zero", "s-lemon", "s-large"}
        if collision != "none":
            store.racks[1].rack_name = prefix + (" another shelf" if collision == "long" else "")
    before = store.model_dump_json()
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = {"name": "Promotion day", "promotions": [{"target": prefix, "kind": promotion, "discount_pct": 50}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/scenario-target", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            result = await describe_scenario(client, "Apply the requested promotion", store)
            changed, lifts = apply_to_store(store, result.scenario)
            items = {item.sku: item for rack in changed.racks for slot in rack.slots for item in slot.items}
            if collision == "none":
                assert result.scenario.promotions[0].target == full
                assert set(lifts) == expected
                assert {sku for sku, item in items.items() if item.promo} == expected
                if promotion == "discount":
                    assert {sku for sku, item in items.items() if item.price == 50} == expected
                assert items["s-beer"].price == 100 and not items["s-beer"].promo
            else:
                assert result.scenario.promotions == [] and not lifts
                assert any("ambiguous" in warning for warning in result.warnings)
                assert all(item.price == 100 and not item.promo for item in items.values())
            assert store.model_dump_json() == before
            assert await describe_scenario(client, "Apply the requested promotion", store) == result
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            if mode == "json_schema":
                assert calls[0]["response_format"]["json_schema"]["schema"]["$defs"]["_Promotion"]["properties"]["target"]["maxLength"] == 80

    asyncio.run(exercise())


@pytest.mark.parametrize("case", ["exact_limit", "keyword", "unknown", "no_store", "duplicate_name"])
def test_existing_full_names_keywords_and_no_store_behavior_are_preserved(case):
    store = target_store()
    target, expected = "cola", {"s-cola", "s-zero", "s-large"}
    if case in {"exact_limit", "duplicate_name"}:
        target = "A" * 80
        store.racks[0].slots[0].items[0].name = target
        expected = {"s-cola"}
        if case == "duplicate_name":
            store.racks[1].slots[0].items[0].name = target
            expected.add("s-beer")
    elif case == "unknown":
        target, expected = "UnlistedTarget" * 6, set()
        target = target[:80]
    draft = ScenarioDraft(name="Day", promotions=[{"target": target, "discount_pct": 50}])
    result = to_scenario(draft, "Promotion", None if case == "no_store" else store)
    assert [p.target for p in result.scenario.promotions] == ([] if case == "unknown" else [target])
    if case != "no_store":
        _, lifts = apply_to_store(store, result.scenario)
        assert set(lifts) == expected


def test_ambiguous_name_does_not_remove_an_independent_valid_promotion():
    store = target_store()
    prefix = "Z" * 80
    store.racks[0].slots[0].items[0].name = prefix + " original"
    store.racks[0].slots[0].items[1].name = prefix + " other"
    draft = ScenarioDraft(name="Day", promotions=[{"target": prefix, "discount_pct": 50},
                                                  {"target": "Lager Beer 500ml", "discount_pct": 20}])
    result = to_scenario(draft, "Two promotions", store)
    assert [p.target for p in result.scenario.promotions] == ["Lager Beer 500ml"]
    changed, lifts = apply_to_store(store, result.scenario)
    assert set(lifts) == {"s-beer"} and changed.racks[1].slots[0].items[0].price == 80
    assert all(item.price == 100 for item in changed.racks[0].slots[0].items)


@pytest.mark.parametrize("case", ["exact_sku", "unique_folded_sku", "ambiguous_folded_sku"])
def test_bounded_name_recovery_keeps_the_existing_sku_precedence(case):
    store = target_store()
    target = "Ab" * 40
    store.racks[0].slots[0].items[0].name = target + " long product name"
    sku = target if case == "exact_sku" else target.lower()
    store.racks[0].slots[0].items[1].sku = sku
    if case == "ambiguous_folded_sku":
        store.racks[0].slots[0].items[2].sku = target.upper()
    result = to_scenario(ScenarioDraft(name="Day", promotions=[{"target": target, "discount_pct": 50}]), "Promotion", store)
    _, lifts = apply_to_store(store, result.scenario)
    assert set(lifts) == (set() if case == "ambiguous_folded_sku" else {sku})
