"""An output-limited free-text summary cannot become customer evidence."""

import asyncio
import io
import json

import httpx
import pytest
from instructor.core.exceptions import IncompleteOutputException
from openpyxl import Workbook

from store_emulator.application.supplemental import summarize_supplemental
from store_emulator.domain.config import LLMConfig
from store_emulator.engine.generators.persona import analyze_location
from store_emulator.engine.llm_client import LiteLLMClient, final_answer_text


@pytest.fixture
def scripted_http(monkeypatch):
    def install(protocol, respond):
        def response(request):
            if request.url.path.endswith("/api/show"):
                return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
            body = json.loads(request.content)
            content, reason = respond(body)
            if protocol == "ollama":
                result = {"model": body["model"], "done": True, "done_reason": reason,
                    "message": {"role": "assistant", "content": content}, "prompt_eval_count": 10, "eval_count": 5}
            else:
                result = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                    "choices": [{"index": 0, "finish_reason": reason, "message": {"role": "assistant", "content": content}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
            return httpx.Response(200, request=request, json=result)
        def send(self, request, *args, **kwargs): return response(request)
        async def asend(self, request, *args, **kwargs): return response(request)
        monkeypatch.setattr(httpx.Client, "send", send)
        monkeypatch.setattr(httpx.AsyncClient, "send", asend)
        return LiteLLMClient(LLMConfig(model="ollama_chat/local-summary" if protocol == "ollama" else "openai/local-summary",
            api_base="http://127.0.0.1:11434" if protocol == "ollama" else "http://127.0.0.1:8081/v1",
            api_key="offline", structured_output="json_schema", max_tokens=160))
    return install


@pytest.mark.parametrize("protocol", ["openai", "ollama"])
@pytest.mark.parametrize("content", ["", "- Customers spend", "- Half visit in the morning."])
def test_raw_length_cutoff_raises_once_and_retains_usage(scripted_http, protocol, content):
    calls = []
    def respond(body):
        calls.append(body)
        return content, "length"
    client = scripted_http(protocol, respond)
    with pytest.raises(IncompleteOutputException):
        asyncio.run(client.generate_text_async("Summarize", "Recorded customer data"))
    usage = client.get_usage()
    assert len(calls) == usage.requests == 1 and usage.total_tokens == 15 and usage.cached_requests == 0


@pytest.mark.parametrize("protocol", ["openai", "ollama"])
@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize("reason", ["length", "stop"])
@pytest.mark.parametrize("content", ["- Customers spend", "- Half visit in the morning.", "<think>Notes</think>\n- Residents spend"])
def test_uploaded_data_does_not_forward_cutoff_summaries_to_customer_generation(scripted_http, protocol, kind, reason, content):
    rows = [["customer", "spend"], ["resident", 3], ["resident", 5]]
    if kind == "csv":
        data = "\n".join(",".join(map(str, row)) for row in rows).encode()
        sheet = "data"
    else:
        book = Workbook()
        book.active.title = sheet = "고객"
        for row in rows:
            book.active.append(row)
        buf = io.BytesIO()
        book.save(buf)
        data = buf.getvalue()
    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return json.dumps({"selected_columns": [{"sheet_name": sheet, "columns": ["customer", "spend"]}]}), "stop"
        if len(calls) == 2:
            return content, reason
        return json.dumps({"keywords": ["nearby"], "identities": ["resident"], "purposes": ["groceries"]}), "stop"
    client = scripted_http(protocol, respond)
    async def exercise():
        summary = await summarize_supplemental(data, f"customers.{kind}", client)
        expected = "" if reason == "length" else final_answer_text(content)
        assert summary == expected
        await analyze_location(client, "Seoul", "동네 주민", supplemental_summary=summary)
        user = next(m["content"] for m in calls[-1]["messages"] if m["role"] == "user")
        assert ("Supplemental data analysis:" in user) is bool(expected)
        if expected:
            assert expected in user
        else:
            assert final_answer_text(content) not in user
        assert len(calls) == client.get_usage().requests == 3
        assert client.get_usage().total_tokens == 45
    asyncio.run(exercise())
