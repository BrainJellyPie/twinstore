"""Provider identity comes from the harness, never from generated report content."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.report import _NarrativeResponse, write_narrative
from tests.engine.test_marketing_report_losses import losing_report


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("metadata", ["omitted", None, {}, ["model"], 42, False, "guessed-model"])
def test_unused_model_metadata_does_not_discard_valid_report_content(monkeypatch, tmp_path, mode, metadata):
    payload = {"summary": "Sales were lower.", "interpretation": "The interval excludes zero.", "next_steps": "Test another price."}
    if metadata != "omitted":
        payload["model"] = metadata
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-report", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            first = await write_narrative(client, losing_report())
            assert first.summary == payload["summary"] and first.interpretation == payload["interpretation"]
            assert first.next_steps == payload["next_steps"] and first.model == ""
            assert (await write_narrative(client, losing_report())).model_dump() == first.model_dump()
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            saved = [json.loads(p.read_text())["result"] for p in tmp_path.rglob("*.json")]
            assert len(saved) == 1 and "model" not in saved[0]

    asyncio.run(exercise())


def test_narrative_schema_only_asks_for_the_report_text():
    schema = _NarrativeResponse.model_json_schema()
    assert set(schema["properties"]) == {"summary", "interpretation", "next_steps"}
