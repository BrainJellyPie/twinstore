"""Malformed model weekday restrictions must not broaden a scenario to every day."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.scenario import apply_to_personas, compile_scenario
from store_emulator.engine.scenario_writer import ScenarioDraft, describe_scenario, to_scenario
from tests.engine.test_shelf_panel_boundaries import person


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("days", [[0], [8], [-1], [0, 8], [1, 0], [7, 8]])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_invalid_weekdays_retry_before_population_filter_and_cache(monkeypatch, tmp_path, mode, days, outcome):
    original, calls = llm_client.litellm.acompletion, []
    bad = {"name": "Friday only", "only_days": days}
    good = {"name": "Friday only", "only_days": [5]}

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        corrected = outcome == "legacy_cache" or outcome == "corrected" and len(calls) > 1
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(good if corrected else bad)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/scenario-model-weekdays", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            args = (client, "Friday only", None)
            if outcome == "legacy_cache":
                await describe_scenario(*args)
                [entry] = list(tmp_path.rglob("*.json"))
                saved = json.loads(entry.read_text())
                saved["result"]["only_days"] = days
                entry.write_text(json.dumps(saved))
            if outcome == "repeated":
                with pytest.raises(InstructorRetryException):
                    await describe_scenario(*args)
                assert not list(tmp_path.rglob("*.json"))
            else:
                result = await describe_scenario(*args)
                assert result.scenario.only_days == [5] and not result.warnings
                people = [person(str(day)).model_copy(update={"day": day}) for day in Weekday]
                chosen = apply_to_personas(people, result.scenario, compile_scenario(result.scenario), seed=0, scale_traffic=False)
                assert len(chosen) == 1 and chosen[0].day == Weekday.FRI
                assert await describe_scenario(*args) == result
                assert client.get_usage().cached_requests == 1
                assert [json.loads(p.read_text())["result"]["only_days"] for p in tmp_path.rglob("*.json")] == [[5]]

    asyncio.run(exercise())
    assert len(calls) == 2
    if mode == "json_schema":
        items = calls[0]["response_format"]["json_schema"]["schema"]["properties"]["only_days"]["items"]
        assert items["minimum"] == 1 and items["maximum"] == 7


@pytest.mark.parametrize("days,expected", [([], list(range(1, 8))), ([1], [1]), ([7], [7]), ([1, 7], [1, 7]), ([7, 1, 7], [1, 7])])
def test_explicit_days_deduplication_and_all_day_default_remain_valid(days, expected):
    result = to_scenario(ScenarioDraft(name="Requested days", only_days=days), "Requested days", None)
    people = [person(str(day)).model_copy(update={"day": day}) for day in Weekday]
    chosen = apply_to_personas(people, result.scenario, compile_scenario(result.scenario), seed=0, scale_traffic=False)
    assert [int(p.day) for p in chosen] == expected
