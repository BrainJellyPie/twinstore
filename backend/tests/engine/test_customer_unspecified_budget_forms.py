"""A blank unspecified budget must not provoke a retry that invents spending limits."""

import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_customer_budget_units import HOURS, PERSON, PROFILE, response_model


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "EUR", "JPY"])
@pytest.mark.parametrize("low,high", [("", "0"), ("0", ""), ("", ""), (" \t", 0), (0, ""), ("", "00.00")])
def test_empty_unbounded_pair_keeps_no_limit_without_reasking(monkeypatch, tmp_path, mode, currency, low, high):
    original, calls = llm_client.litellm.acompletion, []
    payload = {"personas": [{**PERSON, "budget_min_major": low, "budget_max_major": high}]}

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        # A second answer would invent a spending range, as in the actual CPU trace.
        answer = payload if len(calls) == 1 else {"personas": [
            {**PERSON, "budget_min_major": "5", "budget_max_major": "20"}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion",
            "created": 0, "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/unspecified-budget", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                return await gen.generate_personas_for_day(client, "offline", PROFILE, Weekday.MON, HOURS,
                    currency=currency, seed=4, customer_profile="No budget was specified.")

            people = await run()
            assert len(people) == 1 and (people[0].budget_min, people[0].budget_max) == (0, 0)
            assert len(calls) == 1
            assert await run() == people and len(calls) == client.get_usage().cached_requests == 1
            saved = json.loads(next(tmp_path.rglob("*.json")).read_text())["result"]["personas"][0]
            assert (saved["budget_min"], saved["budget_max"]) == (0, 0)
            assert "budget_min_major" not in saved and "budget_max_major" not in saved

    asyncio.run(exercise())


@pytest.mark.parametrize("other", ["20", "0.01", "-0", "0e0", "0,00", "$0", "0" * 17, True, False, None, [], {}])
@pytest.mark.parametrize("reverse", [False, True])
def test_blank_cannot_hide_partial_or_invalid_budget(other, reverse):
    low, high = (other, "") if reverse else ("", other)
    with pytest.raises(ValidationError):
        response_model("USD").model_validate({"personas": [{**PERSON, "budget_min_major": low,
            "budget_max_major": high}]}, strict=True)


def test_normalization_preserves_input_and_wire_shape():
    model = response_model("USD")
    payload = {"personas": [{**PERSON, "budget_min_major": "", "budget_max_major": "0"}]}
    before = deepcopy(payload)
    result = model.model_validate(payload, strict=True)
    assert payload == before
    assert (result.personas[0].budget_min, result.personas[0].budget_max) == (0, 0)
    props = model.model_json_schema()["$defs"]["LabelledPersona"]["properties"]
    assert props["budget_min_major"]["pattern"] == r"^[0-9]{1,16}(\.[0-9]{1,2})?$"
