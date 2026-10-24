"""Only the final data summary, not a local model's explicit thoughts, can become customer evidence."""

import asyncio
import io
import json

import httpx
import pytest
from openai import AsyncOpenAI
from openpyxl import Workbook

from store_emulator.application.supplemental import SUPPLEMENTAL_SUMMARY_MAX_CHARS, summarize_supplemental
from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.generators.persona import analyze_location


FINAL = "- Nearby residents buy tea in the evening.\n- Recorded spending is 3 to 5 dollars."
THOUGHT = "UNCONFIRMED: Perhaps these customers spend 900 dollars each. "
CASES = [
    ("<think>" + THOUGHT * 50 + "</think>\n" + FINAL, FINAL),
    (" \n<think>" + THOUGHT + "</think>\n<think>Check the data.</think>\n" + FINAL, FINAL),
    ("<think>" + THOUGHT, ""),
    ("<think>" + THOUGHT + "</think>\n", ""),
    ("  " + FINAL + "\n", FINAL),
    (FINAL + '\n- A literal label contains "<think>tea</think>".', FINAL + '\n- A literal label contains "<think>tea</think>".'),
    ("<think>" + THOUGHT + "</think>\n" + FINAL * 50, (FINAL * 50)[:SUPPLEMENTAL_SUMMARY_MAX_CHARS]),
]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize("response,expected", CASES,
    ids=["long-thought", "repeated-thoughts", "unfinished-thought", "thought-only", "plain", "literal-tag", "long-final"])
def test_uploaded_data_uses_final_summary_before_storage_limit_and_customer_prompt(monkeypatch, tmp_path, mode, kind, response, expected):
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
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            content = json.dumps({"selected_columns": [{"sheet_name": sheet, "columns": ["customer", "spend"]}]})
        elif len(calls) == 2:
            content = response
        else:
            content = json.dumps({"keywords": ["nearby"], "identities": ["resident"], "purposes": ["groceries"]})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 23, "total_tokens": 34}})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/supplemental-final-answer",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            summary = await summarize_supplemental(data, f"customers.{kind}", client)
            assert summary == expected
            assert len(summary) <= SUPPLEMENTAL_SUMMARY_MAX_CHARS
            await analyze_location(client, "Seoul", "동네 주민", supplemental_summary=summary)
            user = next(m["content"] for m in calls[-1]["messages"] if m["role"] == "user")
            assert "UNCONFIRMED" not in user
            assert ("Supplemental data analysis:" in user) is bool(expected)
            if expected:
                assert expected in user
            assert len(calls) == 3 and client.get_usage().requests == 3
            assert client.get_usage().total_tokens == 102

    asyncio.run(exercise())
