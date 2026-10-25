"""Reversed model ranges must retry rather than cache an impossible shopper search."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.customer import TimelineEvent
from store_emulator.domain.types import Action
from store_emulator.engine import llm_client
from store_emulator.engine.shopper_filter import _Filter, apply_filter, find_shoppers
from tests.engine.test_shopper_filter_boundaries import STORE, customer


def shoppers(currency):
    scale = 100 if currency == "USD" else 1
    return {str(amount): customer(str(amount), spent=amount * scale).model_copy(update={
        "timeline": [TimelineEvent(elapsed_sec=amount * 60, x=0, y=0, action=Action.EXIT)],
    }) for amount in (0, 5, 15, 25)}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["spent", "minutes"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("recovery", ["corrected", "repeated", "legacy_cache"])
def test_reversed_http_ranges_are_corrected_before_search_and_cache(monkeypatch, tmp_path, mode, field, currency, recovery):
    customers = shoppers(currency)
    invalid = {"label": "Range", f"min_{field}": 20, f"max_{field}": 10}
    valid = {"label": "Range", f"min_{field}": 10, f"max_{field}": 20}
    original, calls, retry_later = llm_client.litellm.acompletion, [], False

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        answer = valid if retry_later or recovery == "legacy_cache" or recovery == "corrected" and len(calls) > 1 else invalid
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal retry_later
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shopper-ranges", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            seeded = False
            generate = client.generate_structured_async

            async def generate_with_legacy_cache(schema, system, user, **kwargs):
                nonlocal seeded
                if recovery == "legacy_cache" and not seeded:
                    path = client._cache_path(schema, client._messages(system, user)[0], kwargs.get("seed"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"result": invalid}))
                    seeded = True
                return await generate(schema, system, user, **kwargs)

            monkeypatch.setattr(client, "generate_structured_async", generate_with_legacy_cache)

            async def search():
                return await find_shoppers(client, f"Find shoppers with {field} from 10 to 20", customers, {}, STORE, currency)

            if recovery == "repeated":
                with pytest.raises(InstructorRetryException):
                    await search()
                assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await search()
            assert result.persona_ids == ["15"] and not result.warnings
            assert result.total == 4 and len(result.criteria) == 2
            assert await search() == result
            assert len(calls) == {"corrected": 2, "repeated": 3, "legacy_cache": 1}[recovery]
            assert client.get_usage().cached_requests == 1
            if recovery != "legacy_cache":
                feedback = json.dumps(calls[1]["messages"])
                assert f"min_{field}" in feedback and f"max_{field}" in feedback
            assert all(json.loads(path.read_text())["result"][f"min_{field}"] == 10 for path in tmp_path.rglob("*.json"))

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["spent", "minutes"])
@pytest.mark.parametrize("bounds,expected", [((0, 0), ["0"]), ((15, 15), ["15"]),
    ((None, 0), ["0"]), ((15, None), ["25", "15"]), ((None, None), ["25", "15", "5", "0"])])
def test_equal_zero_and_one_sided_model_ranges_remain_valid(field, bounds, expected):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Range", f"min_{field}": bounds[0], f"max_{field}": bounds[1]})

    result = asyncio.run(find_shoppers(Model(), "Find shoppers", shoppers("USD"), {}, STORE, "USD"))
    assert result.persona_ids == expected


def test_explicit_legacy_filter_keeps_its_existing_empty_result():
    result = apply_filter(_Filter(label="Legacy", min_spent=20, max_spent=10), shoppers("USD"), {}, STORE, "USD")
    assert not result.persona_ids and len(result.criteria) == 2 and result.near_misses
