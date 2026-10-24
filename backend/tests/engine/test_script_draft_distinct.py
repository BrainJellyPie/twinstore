"""A cached copy of the control script must not masquerade as a usable test alternative."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.staff_pitch import PitchRequest
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.script_writer import draft_script


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("copied", ["Would you like tea?", "WOULD YOU LIKE TEA?", "\tWould  you\nlike tea? \u3000"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_copied_scripts_retry_before_builder_validation_and_cache(monkeypatch, tmp_path, mode, copied, outcome):
    current = "Would you like tea?"
    good = {"name": "Value first", "script": "Tea is $2. Would you like one?", "differs_by": ""}
    bad = {**good, "script": copied}
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        invalid = phase == "invalid" and not (outcome == "corrected" and len(requests) > 1)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(bad if invalid else good)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/distinct-script", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def draft():
                return await draft_script(client, product="Tea", offer="$2", context="At the shelf", facts="500 ml", current=current)

            if outcome == "legacy_cache":
                await draft()
                paths = list(tmp_path.rglob("*.json"))
                assert len(paths) == 1
                saved = json.loads(paths[0].read_text())
                saved["result"] = bad
                paths[0].write_text(json.dumps(saved))
                phase = "invalid"
            if outcome in {"repeated", "legacy_cache"}:
                before = len(requests)
                with pytest.raises(InstructorRetryException):
                    await draft()
                assert len(requests) == before + 2
                if outcome == "repeated":
                    assert not list(tmp_path.rglob("*.json"))
                phase = "complete"
            result = await draft()
            assert result.model_dump() == good
            request = PitchRequest(setup_id="setup", sku="tea", context="At the shelf", variants=[
                {"name": "Control", "script": current}, {"name": result.name, "script": result.script}])
            assert request.variants[0].script == current and request.variants[1].script == good["script"]
            if outcome == "corrected":
                assert len(requests) == 2
            before = len(requests)
            assert (await draft()).model_dump() == good and len(requests) == before
            assert [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")] == [good]

    asyncio.run(exercise())


@pytest.mark.parametrize("current,script", [("", "Would you like tea?"), (" \t\u3000", "Would you like tea?"),
    ("차를 드릴까요?", "차 한 잔 어떠세요?"), ("Would you like tea?", "Would you like a cup of tea?")])
def test_first_scripts_and_actual_alternatives_remain_usable(current, script):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"name": "Alternative", "script": script, "differs_by": None})

    result = asyncio.run(draft_script(Model(), product="Tea", offer="$2", context="At the shelf", facts="", current=current))
    assert result.script == script and result.differs_by == ""
