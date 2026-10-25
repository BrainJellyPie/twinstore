"""Large rival comparisons split only after typed capacity failures, preserving every requested row."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.shelf_lab.rival_match import match_products


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("capacity", [1, 3, 8])
@pytest.mark.parametrize("failure", ["length", "context"])
@pytest.mark.parametrize("extra_rows", ["single", "contradictory", "unmatched"])
def test_capacity_failure_retries_same_rows_in_smaller_learned_batches(monkeypatch, tmp_path, mode, capacity, failure, extra_rows):
    rivals = [f"Rival tea {i}" for i in range(9)]
    ours = [f"Our tea {i}" for i in range(9)]
    original, calls, succeeded = llm_client.litellm.acompletion, [], []

    def respond(request):
        body = json.loads(request.content)
        prompt = next(row["content"] for row in body["messages"] if row["role"] == "user" and "Rival products:\n" in row["content"])
        asked = [line.removeprefix("- ") for line in prompt.split("Rival products:\n", 1)[1].splitlines()]
        calls.append(asked)
        if len(asked) > capacity and failure == "context":
            return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                "message": "request (9000 tokens) exceeds the available context size (8192 tokens)"}})
        truncated = len(asked) > capacity
        pairs = [{"rival": name, "ours": ours[rivals.index(name)]} for name in asked]
        if not truncated:
            succeeded.append(asked)
            if rivals[0] not in asked:
                # A small model can repeat a product from an earlier task. It is not part of this batch.
                pairs.append({"rival": rivals[0], "ours": ours[1]})
                if extra_rows != "single":
                    pairs.append({"rival": rivals[0], "ours": ours[0] if extra_rows == "contradictory" else None})
        content = '{"pairs":[' if truncated else json.dumps({"pairs": pairs})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if truncated else "stop",
                "message": {"role": "assistant", "content": content}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-batches", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path), max_parallel=1))
            expected = dict(zip(rivals, ours, strict=True))
            assert await asyncio.wait_for(match_products(client, rivals, ours), timeout=5) == expected
            assert [name for batch in succeeded for name in batch] == rivals
            learned = len(succeeded[0])
            first_success = next(i for i, batch in enumerate(calls) if len(batch) <= capacity)
            assert all(len(batch) <= learned for batch in calls[first_success:])
            before = len(succeeded)
            assert await asyncio.wait_for(match_products(client, rivals, ours), timeout=5) == expected
            assert len(succeeded) == before  # successful smaller tasks are cached

    asyncio.run(exercise())


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("failure", ["authentication", "forbidden_context", "unrelated_bad_request", "invalid_json", "conflict", "late_auth",
                                     "single_length", "single_context"])
def test_noncapacity_terminal_failures_do_not_fan_out(monkeypatch, mode, failure):
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if failure in {"authentication", "late_auth", "forbidden_context", "unrelated_bad_request", "single_context"} and not (failure == "late_auth" and len(calls) == 1):
            code = 401 if failure in {"authentication", "late_auth"} else 403 if failure == "forbidden_context" else 400
            message = ("request (9000 tokens) exceeds the available context size (8192 tokens)"
                       if failure in {"forbidden_context", "single_context"} else "incorrect api key" if code == 401 else "unsupported model")
            return httpx.Response(code, request=request, json={"error": {"message": message}})
        content = json.dumps({"pairs": [{"rival": "Label", "ours": "Tea"}, {"rival": "Label", "ours": ""}]}) if failure == "conflict" else '{"pairs":['
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if failure in {"late_auth", "single_length"} else "stop",
                "message": {"role": "assistant", "content": content}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-failures", api_base="http://127.0.0.1:8081/v1", structured_output=mode))
            with pytest.raises(InstructorRetryException):
                await match_products(client, ["Label"] if failure.startswith("single_") else ["Label", "Other"], ["Tea"])
            assert len(calls) == 2

    asyncio.run(exercise())


def test_unasked_product_beyond_existing_eighty_row_cap_is_not_accepted():
    rivals = [f"Label {i}" for i in range(81)]

    class Model:
        async def generate_structured_async(self, schema, prompt, user, **kwargs):
            assert "- Label 80" not in user
            return schema.model_validate({"pairs": [{"rival": "Label 80", "ours": "Tea"},
                                                    {"rival": "Label 80", "ours": "Coffee"}]})

    assert asyncio.run(match_products(Model(), rivals, ["Tea", "Coffee"])) == {}
