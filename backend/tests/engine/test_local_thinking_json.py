"""Explicit leading thinking blocks must not become, or corrupt, a structured answer."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import IncompleteOutputException, InstructorRetryException
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client


class Reply(BaseModel):
    value: int
    text: str = ""


async def exercise(monkeypatch, tmp_path, mode, method, content, *, finish="stop", expect_error=False, attempts=1):
    original_sync, original_async = llm_client.litellm.completion, llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 23, "total_tokens": 34}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as ah:
        with httpx.Client(transport=httpx.MockTransport(respond)) as sh:
            sync = OpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=sh, max_retries=0)
            async_client = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=ah, max_retries=0)

            def completion(**kwargs):
                return original_sync(**{**kwargs, "client": sync, "api_key": "offline", "num_retries": 0})

            async def acompletion(**kwargs):
                return await original_async(**{**kwargs, "client": async_client, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "completion", completion)
            monkeypatch.setattr(llm_client.litellm, "acompletion", acompletion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-thinking", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def ask():
                args = (Reply, "Reply", "Give the result")
                if method == "sync":
                    return client.generate_structured(*args, max_retries=attempts)
                if method == "sync_image":
                    return client.generate_structured_with_image(*args, "data:image/png;base64,AA==", max_retries=attempts)
                if method == "async_image":
                    return await client.generate_structured_with_image_async(*args, "data:image/png;base64,AA==", max_retries=attempts)
                return await client.generate_structured_async(*args, max_retries=attempts)

            if expect_error:
                with pytest.raises(InstructorRetryException) as caught:
                    await ask()
                if finish == "length":
                    assert isinstance(caught.value.failed_attempts[-1].exception, IncompleteOutputException)
                assert not list(tmp_path.rglob("*.json")) and len(calls) == attempts
                return None
            first = await ask()
            assert first.model_dump() == (await ask()).model_dump() and len(calls) == 1
            usage = client.get_usage()
            assert (usage.requests, usage.cached_requests, usage.prompt_tokens, usage.completion_tokens) == (2, 1, 11, 23)
            return Reply.model_validate(first.model_dump())


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("method", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("wrapper", ["<think>Example: {\"value\": 99}</think>\n",
    " \n<think>{\"value\": 99}</think>\n<think>다시 검토 {\"value\": 88}</think>\n```json\n"])
def test_final_json_after_explicit_thinking_is_the_only_cached_result(monkeypatch, tmp_path, mode, method, wrapper):
    content = wrapper + '{"value": 7, "text": "final"}' + ('\n```' if wrapper.endswith('```json\n') else '')
    result = asyncio.run(exercise(monkeypatch, tmp_path, mode, method, content))
    assert result == Reply(value=7, text="final")


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("content", ['<think>{"value": 99}</think>', '<think>{"value": 99}',
    '<think>{"value": 99}</think> No final answer', '<think>Example</think>{"value": "wrong type"}'])
def test_reasoning_only_or_invalid_final_output_is_not_a_valid_answer(monkeypatch, tmp_path, mode, content):
    asyncio.run(exercise(monkeypatch, tmp_path, mode, "async", content, expect_error=True, attempts=2))


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("content", ['<think>{"value": 99}</think>{"value": 7}', '<think>{"value": 99}'])
def test_reasoning_cleanup_does_not_turn_truncated_output_into_success(monkeypatch, tmp_path, mode, content):
    asyncio.run(exercise(monkeypatch, tmp_path, mode, "async_image", content, finish="length", expect_error=True))


@pytest.mark.parametrize("prefix,suffix", [("", ""), ("Here is the result: ", " Done."), ("```json\n", "\n```")])
def test_tags_inside_actual_json_values_and_existing_prose_wrappers_are_preserved(monkeypatch, tmp_path, prefix, suffix):
    answer = Reply(value=7, text='<think>{"literal": true}</think>')
    result = asyncio.run(exercise(monkeypatch, tmp_path, "json", "async", prefix + answer.model_dump_json() + suffix))
    assert result == answer


def test_legacy_cache_cannot_reuse_an_answer_extracted_from_unfinished_thinking(monkeypatch, tmp_path):
    # Recorded with this Reply schema/config/messages before final-answer parsing.
    digest = "e6202cf7ec36bf60dfcc38c34721ee294831ddc7688b0894af5bcce08f9d8f4a"
    legacy = tmp_path / digest[:2] / f"{digest}.json"
    legacy.parent.mkdir()
    legacy.write_text(json.dumps({"result": {"value": 99, "text": ""}}))
    result = asyncio.run(exercise(monkeypatch, tmp_path, "json", "async", '{"value": 7}'))
    assert result.value == 7 and legacy.exists()


def test_raw_text_response_keeps_its_existing_behavior(monkeypatch):
    from tests.engine.test_local_structured_retry_budget import ask

    content = ' \n<think>{"value": 99}</think>\nA plain response.'

    def respond(request):
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": content}}]})

    assert asyncio.run(ask(monkeypatch, "raw", "http://127.0.0.1:8081/v1", respond)) == content
