"""Invalid model event windows must not silently extend traffic until midnight."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.scenario import compile_scenario
from store_emulator.engine.scenario_writer import ScenarioDraft, describe_scenario, to_scenario


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("start,end", [(18, 18), (21, 18), (22, 2)])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_actual_sdk_corrects_event_hours_before_traffic_compilation_and_cache(monkeypatch, tmp_path, provider, mode, start, end, outcome):
    good = {"name": "Evening game", "events": [{"kind": "sports_match", "intensity": 1, "start_hour": 18, "end_hour": 22}]}
    bad = {"name": "Evening game", "events": [{"kind": "sports_match", "intensity": 1, "start_hour": start, "end_hour": end}]}
    calls = []
    retry_later = False

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        payload = good if outcome == "legacy_cache" or retry_later or outcome == "corrected" and len(calls) > 1 else bad
        content = json.dumps(payload)
        if provider == "ollama":
            answer = {"model": "event-hours", "done": True, "done_reason": "stop",
                      "message": {"role": "assistant", "content": content}, "prompt_eval_count": 10, "eval_count": 5}
        else:
            answer = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                      "choices": [{"index": 0, "finish_reason": "stop",
                                   "message": {"role": "assistant", "content": content}}]}
        return httpx.Response(200, request=request, json=answer)

    def send(self, request, *args, **kwargs): return response(request)
    async def asend(self, request, *args, **kwargs): return response(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model=f"{'ollama_chat' if provider == 'ollama' else 'openai'}/event-hours",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))

    async def exercise():
        nonlocal retry_later
        args = (client, "Sports match from 18 to 22", None)
        if outcome == "legacy_cache":
            await describe_scenario(*args)
            [entry] = list(tmp_path.rglob("*.json"))
            data = json.loads(entry.read_text())
            data["result"]["events"] = bad["events"]
            entry.write_text(json.dumps(data))
        if outcome == "repeated":
            with pytest.raises(InstructorRetryException):
                await describe_scenario(*args)
            assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
            retry_later = True
        result = await describe_scenario(*args)
        event = result.scenario.events[0]
        assert (event.start_hour, event.end_hour) == (18, 22)
        effects = compile_scenario(result.scenario)
        assert [h for h in range(24) if effects.traffic(h) > 1] == [18, 19, 20, 21]
        assert len(calls) == (3 if outcome == "repeated" else 2)
        if outcome != "legacy_cache":
            assert "end hour must be later" in json.dumps(calls[1]["messages"])
        assert await describe_scenario(*args) == result and client.get_usage().cached_requests == 1
        [entry] = list(tmp_path.rglob("*.json"))
        assert json.loads(entry.read_text())["result"]["events"][0]["end_hour"] == 22

    asyncio.run(exercise())


@pytest.mark.parametrize("start,end", [(0, 24), (0, 1), (23, 24), (18, 22)])
def test_valid_event_boundaries_keep_exact_traffic_hours(start, end):
    draft = ScenarioDraft.model_validate_json(json.dumps({"name": "Game", "events": [
        {"kind": "sports_match", "intensity": 1, "start_hour": start, "end_hour": end}]}), strict=True)
    result = to_scenario(draft, "Game", None)
    effects = compile_scenario(result.scenario)
    assert [h for h in range(24) if effects.traffic(h) > 1] == list(range(start, end))
