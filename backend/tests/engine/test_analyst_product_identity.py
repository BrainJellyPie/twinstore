"""The model's fact sheet must count product identities rather than shared display names."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.types import Action
from store_emulator.engine import llm_client
from store_emulator.engine.run_analyst import answer_run_question, run_facts
from tests.engine.test_shopper_filter_boundaries import STORE


def purchases(first="regular", second="oat", names=("Milk", "Milk", "Milk")):
    events = [TimelineEvent(elapsed_sec=index, x=0, y=0, action=Action.BUY, product_sku=sku,
        product_name=name, price=price, quantity=quantity, origin=origin)
        for index, (sku, name, price, quantity, origin) in enumerate([
            (first, names[0], 100, 2, "planned"), (second, names[1], 500, 1, "impulse"),
            (first, names[2], 200, 1, "impulse")])]
    return [CustomerResult(persona_id="p", day=1, arrival_time="12:00:00", timeline=events, total_spent=900)]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("first,second", [("regular", "oat"), ("milk", "MILK"), ("Milk", "")])
def test_http_same_name_products_keep_their_own_sales_and_citations(monkeypatch, tmp_path, mode, currency, first, second):
    customers = purchases(first, second)
    before = [c.model_dump() for c in customers]
    money = (lambda value: f"${value / 100:.2f}") if currency == "USD" else (lambda value: f"{value}원")
    first_line = f"Milk (SKU {first}) 3 / {money(400)} / 1"
    second_line = f"Milk (SKU {second}) 1 / {money(500)} / 1" if second else f"Milk (SKU unavailable) 1 / {money(500)} / 1"
    merged = f"Milk 4 / {money(900)} / 2"
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        user = next(message["content"] for message in body["messages"] if message["role"] == "user")
        assert first_line in user and second_line in user and merged not in user
        assert user.index(second_line) < user.index(first_line)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                "content": json.dumps({"answer": "The two product identities have different sales.",
                                       "figures": [first_line, second_line, merged]})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/analyst-products", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                sheet = run_facts(customers, {}, STORE, currency)
                result = await answer_run_question(client, sheet, "How do these two products compare?", [])
                assert result.figures == [first_line, second_line]
                assert f"Revenue: {money(900)}" in sheet and "Impulse units: 2 of 4" in sheet
                assert [c.model_dump() for c in customers] == before
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


def test_one_sku_with_changed_display_names_is_one_product():
    sheet = run_facts(purchases("same", "same", ("Milk", "New label", "Milk")), {}, STORE, "USD")
    assert "Milk 4 / $9.00 / 2" in sheet and "New label" not in sheet


def test_distinct_display_names_keep_the_existing_readable_labels():
    sheet = run_facts(purchases(names=("Cow milk", "Oat milk", "Cow milk")), {}, STORE, "USD")
    assert "Cow milk 3 / $4.00 / 1" in sheet and "Oat milk 1 / $5.00 / 1" in sheet and "(SKU" not in sheet


def test_legacy_name_only_records_still_group_when_no_identity_exists():
    sheet = run_facts(purchases("", ""), {}, STORE, "USD")
    assert "Milk 4 / $9.00 / 2" in sheet and "(SKU" not in sheet
