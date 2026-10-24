"""A malformed model clock must not widen a timed search to everyone."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.shopper_filter import find_shoppers
from tests.engine.test_shopper_filter_boundaries import STORE, customer


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["arrived_after", "arrived_before"])
@pytest.mark.parametrize("invalid", ["15:60", "25:00", "3 pm", "15:00:bad", "24:01", "-1:00"])
@pytest.mark.parametrize("recovers", [False, True])
def test_invalid_model_times_are_corrected_before_matching_and_caching(monkeypatch, tmp_path, mode, field, invalid, recovers):
    customers = {pid: customer(pid, arrival=clock) for pid, clock in [
        ("early", "14:00:00"), ("boundary", "15:30:00"), ("late", "16:00:00")]}
    calls, retry_later = [], False
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        clock = "15:30" if retry_later or recovers and len(calls) > 1 else invalid
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"label": "Timed search", field: clock})}}]})

    async def exercise():
        nonlocal retry_later
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/filter-clocks", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def search():
                return await find_shoppers(client, "Find shoppers around 15:30", customers, {}, STORE, "USD")

            if not recovers:
                with pytest.raises(InstructorRetryException):
                    await search()
                assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await search()
            assert result.persona_ids == (["boundary", "late"] if field == "arrived_after" else ["early"])
            assert result.total == 3 and not result.warnings
            assert await search() == result and len(calls) == (2 if recovers else 3)
            feedback = json.dumps(calls[1]["messages"])
            assert field in feedback and "HH:MM" in feedback

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["arrived_after", "arrived_before"])
@pytest.mark.parametrize("clock", ["", "0:00", "00:00:00", "9:05", "15:30:01", "23:59:59", "24:00", " 15:30 "])
def test_existing_clock_forms_remain_usable(field, clock):
    customers = {"p": customer("p", arrival="15:30:01")}

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Clock", field: clock})

    result = asyncio.run(find_shoppers(Model(), "Find shoppers", customers, {}, STORE, "USD"))
    assert not result.warnings
