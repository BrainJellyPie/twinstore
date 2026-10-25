"""Model choice spelling must preserve the actual selected shoppers and their order."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.customer import TimelineEvent
from store_emulator.domain.persona import AGE_GROUPS, GENDERS
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Action
from store_emulator.engine import llm_client
from store_emulator.engine.shopper_filter import _Filter, find_shoppers
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_shopper_filter_boundaries import STORE, customer

CHOICES = {"age_groups": AGE_GROUPS, "genders": GENDERS, "bought": ["any", "yes", "no"],
           "bought_there": ["any", "yes", "no"], "sort": ["spent", "nothing", "impulse", "longest"]}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field,value", [(field, value) for field, values in CHOICES.items() for value in values])
def test_http_choices_select_real_records_in_the_requested_order(monkeypatch, tmp_path, mode, field, value):
    store = STORE.model_copy(update={"racks": [Rack(id=rid, type="shelf", shape=[[1]], position=(x, 1), rack_name=name,
        slots=[Slot(block=0, face="E", items=[SlotItem(sku="tea", name="Tea box", price=100)])])
        for rid, x, name in [("r1", 1, "Tea"), ("r2", 3, "Snacks")]]})
    personas, customers = {}, {}
    for index, (age, gender) in enumerate(((age, gender) for age in AGE_GROUPS for gender in GENDERS), 1):
        pid = f"p{index:02d}"
        personas[pid] = _persona().model_copy(update={"id": pid, "age_group": age, "gender": gender})
        events = [TimelineEvent(elapsed_sec=i, x=0, y=0, action=Action.BROWSE, target_rack="r1")
                  for i in range(13 - index)]
        if index % 4:
            events.append(TimelineEvent(elapsed_sec=20, x=0, y=0, action=Action.BUY, product_sku="tea",
                target_rack="r1" if index % 2 == 0 else "r2", price=100, quantity=index,
                origin="impulse" if index % 3 == 0 else "planned"))
        events.append(TimelineEvent(elapsed_sec=(13 - index) * 60, x=0, y=0, action=Action.EXIT))
        customers[pid] = customer(pid, spent=index * 100 if index % 4 else 0).model_copy(update={"timeline": events})
    before = [entry.model_dump() for entry in [store, *personas.values(), *customers.values()]]
    variant = f"\u3000{value.swapcase()}\t"
    payload = {"label": "Requested shoppers", field: [variant] if field in ("age_groups", "genders") else variant}
    if field == "bought_there":
        payload["stopped_at"] = ["Tea"]
    expected = []
    for index, pid in enumerate(personas, 1):
        match = (personas[pid].age_group == value if field == "age_groups" else
                 personas[pid].gender == value if field == "genders" else
                 (index % 4 != 0) == (value == "yes") if field == "bought" and value != "any" else
                 (index % 4 == 2) == (value == "yes") if field == "bought_there" and value != "any" else True)
        if match:
            score = index if index % 4 else 0
            if field == "sort" and value in ("nothing", "longest"):
                score = 13 - index
            elif field == "sort" and value == "impulse":
                score = index if index % 3 == 0 and index % 4 else 0
            expected.append((-score, pid))
    expected_ids = [pid for _, pid in sorted(expected)]
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shopper-choices", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                result = await find_shoppers(client, "Find the requested group", customers, personas, store, "USD")
                assert result.persona_ids == expected_ids and result.total == 12
                assert result.sort == (value if field == "sort" else "spent") and not result.warnings
                assert [entry.model_dump() for entry in [store, *personas.values(), *customers.values()]] == before
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("field", CHOICES)
@pytest.mark.parametrize("value", ["unknown", "", "20대", "woman", "y e s", 1, True, None, [], {}])
def test_unknown_choices_and_wrong_types_remain_errors(field, value):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            payload = {"label": "Invalid", field: [value] if field in ("age_groups", "genders") else value}
            return schema.model_validate_json(json.dumps(payload), strict=True)

    with pytest.raises(ValidationError):
        asyncio.run(find_shoppers(Model(), "Find shoppers", {}, {}, STORE, "USD"))


@pytest.mark.parametrize("field", ["age_groups", "genders"])
def test_explicit_null_group_does_not_silently_widen_the_search(field):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate_json(json.dumps({"label": "Invalid", field: None}), strict=True)

    with pytest.raises(ValidationError):
        asyncio.run(find_shoppers(Model(), "Find shoppers", {}, {}, STORE, "USD"))


def test_explicit_legacy_filter_remains_strict():
    with pytest.raises(ValidationError):
        _Filter(label="Legacy", sort="SPENT")
