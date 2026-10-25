"""Absent optional commentary text must not discard a valid required summary."""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.reading import _Commentary, read_study
from store_emulator.engine.marketing.report import _NarrativeResponse, write_narrative
from tests.engine.test_marketing_report_losses import losing_report


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("surface", ["study", "experiment"])
@pytest.mark.parametrize("absent", ["interpretation", "next_steps", "both", "omitted", "empty"])
def test_actual_sdk_keeps_summary_normalizes_absent_details_and_caches_once(monkeypatch, tmp_path, provider, mode, surface, absent):
    payload = {"summary": "The estimate is uncertain; the interval includes zero.",
               "interpretation": "The results do not establish a cause.", "next_steps": "Compare with a real panel."}
    if absent == "omitted":
        payload.pop("interpretation")
        payload.pop("next_steps")
    elif absent in {"both", "empty"}:
        payload.update(interpretation="" if absent == "empty" else None, next_steps="" if absent == "empty" else None)
    else:
        payload[absent] = None
    expected = {key: value or "" for key, value in {"interpretation": "", "next_steps": "", **payload}.items()}
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        content = json.dumps(payload)
        if provider == "ollama":
            answer = {"model": "commentary-details", "done": True, "done_reason": "stop",
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
    client = LiteLLMClient(LLMConfig(model=f"{'ollama_chat' if provider == 'ollama' else 'openai'}/commentary-details",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))
    for _ in range(2):
        reply = asyncio.run(read_study(client, "concept test", '{"respondents":20}', "Why?", []) if surface == "study"
                            else write_narrative(client, losing_report()))
        assert {key: getattr(reply, key) for key in expected} == expected and len(calls) == 1
    assert [json.loads(path.read_text())["result"] for path in tmp_path.glob("*/*.json")] == [expected]


@pytest.mark.parametrize("schema", [_Commentary, _NarrativeResponse])
@pytest.mark.parametrize("summary", [None, "", " \n\t", False, {}, []])
def test_summary_still_requires_nonblank_text(schema, summary):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({"summary": summary, "interpretation": "", "next_steps": ""}), strict=True)


@pytest.mark.parametrize("schema", [_Commentary, _NarrativeResponse])
@pytest.mark.parametrize("field", ["interpretation", "next_steps"])
@pytest.mark.parametrize("value", [False, 17, {}, []])
def test_non_text_details_are_not_coerced(schema, field, value):
    body = {"summary": "There is no clear winner.", "interpretation": "", "next_steps": "", field: value}
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps(body), strict=True)
