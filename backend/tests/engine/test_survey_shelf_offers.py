"""Survey drafting must not price an image from the last placement of its SKU."""

import json

import httpx
import pytest

from store_emulator.application import shelf_lab, study_design
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.prompting import display_price
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("reverse", [False, True])
def test_every_distinct_shelf_offer_reaches_design_and_changed_prices_invalidate_cache(monkeypatch, tmp_path, currency, mode, reverse):
    store, _ = fixture()
    store.currency = currency
    regular = store.racks[0]
    regular.rack_name = "Regular shelf"
    item = regular.slots[0].items[0]
    item.name, item.price = "Tea", 299
    regular.slots[0].items.append(item.model_copy(deep=True))
    promo = regular.model_copy(deep=True, update={"id": "promo", "rack_name": "Promo shelf"})
    for product in promo.slots[0].items:
        product.price = 99
    store.racks = [promo, regular] if reverse else [regular, promo]
    monkeypatch.setattr(study_design, "_store_for", lambda *args: store)
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: [shelf_lab.PackageAsset(
        asset_id="pack", name="Tea pack", width=10, height=10, sku=item.sku)])
    client = LiteLLMClient(LLMConfig(model="openai/survey-offers", api_base="http://127.0.0.1:8081/v1",
        api_key="offline", structured_output=mode, cache_dir=str(tmp_path)))
    monkeypatch.setattr(study_design, "assistive_client", lambda *args: client)
    calls = []
    reference = 299
    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        expected = f"Tea at {display_price(reference, currency)} on Regular shelf"
        value = reference / 100 if currency == "USD" else reference
        answer = {"name": "Tea value", "images": ["Tea pack"], "questions": ["value", "open"],
            "reference_price": value if expected in user else None}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    req = study_design.SurveyDesignRequest(question="Would the Regular shelf's tea be worth its shown price?", setup_id="s", currency=currency)
    for index, reference in enumerate([299, 399], 1):
        for product in regular.slots[0].items:
            product.price = reference
        before = store.model_dump_json()
        result = study_design.design_concept("p", req, SimulationConfig())
        assert result.reference_price == reference and result.stimuli == ["pack"]
        assert study_design.design_concept("p", req, SimulationConfig()) == result
        assert len(calls) == index and client.get_usage().cached_requests == index
        user = next(m["content"] for m in calls[-1]["messages"] if m["role"] == "user")
        assert user.count(f"Tea at {display_price(reference, currency)} on Regular shelf") == 1
        assert user.count(f"Tea at {display_price(99, currency)} on Promo shelf") == 1
        assert store.model_dump_json() == before


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("same_money", [False, True])
def test_many_offers_keep_the_asked_shelf_with_a_bounded_truthful_listing(monkeypatch, reverse, same_money):
    store, _ = fixture()
    store.currency = "USD"
    base = store.racks[0]
    base.slots[0].items[0].name = "Tea"
    racks = []
    for i in range(40):
        rack = base.model_copy(deep=True, update={"id": f"s{i}", "rack_name": "Backcorner" if i == 17 else f"Display{i}"})
        rack.slots[0].items[0].price = 100 + i
        racks.append(rack)
    store.racks = list(reversed(racks)) if reverse else racks
    monkeypatch.setattr(study_design, "_store_for", lambda *args: store)
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: [shelf_lab.PackageAsset(
        asset_id="pack", name="Tea pack", width=10, height=10, sku=base.slots[0].items[0].sku)])
    prompts = []
    class Designer:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            prompts.append(user)
            return schema(name="Tea study", images=["Tea pack"], questions=["open"], reference_price=None)
    monkeypatch.setattr(study_design, "assistive_client", lambda *args: Designer())
    study_design.design_concept("p", study_design.SurveyDesignRequest(question="Would Backcorner tea appeal to residents?",
        setup_id="s", currency="USD" if same_money else "KRW"), SimulationConfig())
    user = prompts[0]
    assert "on Backcorner" in user
    assert user.count(" on ") == 4 and "36 additional shelf offers omitted" in user
    assert ("$1.17" in user) is same_money
    if not same_money:
        assert "$" not in user and " at " not in user
