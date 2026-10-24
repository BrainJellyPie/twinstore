"""In-flight negotiation retries must respect a newly selected local server's capacity."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from tests.engine.test_local_output_budget_recovery import rejection


class Reply(BaseModel):
    text: str


@pytest.mark.parametrize("mode", ["text", "image", "raw"])
@pytest.mark.parametrize("kind", ["option", "budget"])
@pytest.mark.parametrize("old_limit", [None, 4])
@pytest.mark.parametrize("new_limit", [1, 2])
def test_late_rejection_reacquires_the_new_endpoints_slots(monkeypatch, tmp_path, mode, kind, old_limit, new_limit):
    monkeypatch.setattr(llm_client, "_REJECTED", {})
    original = llm_client.litellm.acompletion
    first = LLMConfig(model="openai/shared-local-name", api_base="http://127.0.0.1:8081/v1",
        max_parallel=old_limit, max_tokens=8192, structured_output="json_schema", cache_dir=str(tmp_path))
    second = first.model_copy(update={"api_base": "http://127.0.0.1:8082/v1", "max_parallel": new_limit,
                                      "max_tokens": 4096})
    arrived, advanced, saturated = asyncio.Event(), asyncio.Event(), asyncio.Event()
    old_calls = new_active = peak = 0
    sent = []
    reroutes = []

    def reroute(model, error):
        reroutes.append(model)
        return second

    async def respond(request):
        nonlocal old_calls, new_active, peak
        body = json.loads(request.content)
        text = str(body["messages"])
        sent.append((request.url.port, body))
        if request.url.port == 8081:
            old_calls += 1
            if old_calls == 4:
                arrived.set()
            await arrived.wait()
            if "switch-provider" in text:
                return httpx.Response(401, request=request, json={"error": {
                    "message": "invalid api key", "type": "authentication_error"}})
            await advanced.wait()
            message = ("Unsupported parameter: temperature is not supported" if kind == "option"
                       else rejection(8192, 4096, 1024))
            return httpx.Response(400, request=request, json={"error": {"message": message, "type": "BadRequestError"}})
        advanced.set()
        new_active += 1
        peak = max(peak, new_active)
        if new_active >= new_limit:
            saturated.set()
        try:
            await saturated.wait()
            # Yield to every already-ready retry while the server is occupied.
            for _ in range(8):
                await asyncio.sleep(0)
            return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
                "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"text":"ready"}'}}]})
        finally:
            new_active -= 1

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
            adapters = {base: AsyncOpenAI(api_key="offline", base_url=base, http_client=transport, max_retries=0)
                        for base in (first.api_base, second.api_base)}

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapters[kwargs["api_base"]], "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(first, reroute=reroute)

            async def ask(prompt):
                if mode == "raw":
                    return await client.generate_text_async("Reply", prompt)
                if mode == "image":
                    return await client.generate_structured_with_image_async(Reply, "Reply", prompt, "data:image/png;base64,AA==")
                return await client.generate_structured_async(Reply, "Reply", prompt)

            replies = await asyncio.wait_for(asyncio.gather(*(ask(prompt) for prompt in
                ["customer-0", "customer-1", "customer-2", "switch-provider"])), 5)
            assert all((reply if mode == "raw" else reply.text) == ('{"text":"ready"}' if mode == "raw" else "ready") for reply in replies)
            assert new_active == 0
            assert peak == new_limit
            assert len(sent) == 8
            assert reroutes == [first.model]
            assert all(body["max_tokens"] == 4096 and body.get("temperature") == second.temperature
                       for port, body in sent if port == 8082)
            # Nothing returned by the fallback can be reused as an old-endpoint answer.
            old_client = llm_client.LiteLLMClient(first)
            for prompt in ["customer-0", "customer-1", "customer-2", "switch-provider"]:
                messages, _ = (old_client._messages_with_image("Reply", prompt, "data:image/png;base64,AA==")
                               if mode == "image" else old_client._messages("Reply", prompt))
                assert old_client._cache_get(old_client._cache_path(Reply, messages, None), Reply) is None

    asyncio.run(exercise())


@pytest.mark.parametrize("transitions", [1, 7])
def test_switching_again_while_queued_does_not_send_stale_requests_or_consume_retry_budget(monkeypatch, transitions):
    from litellm import ModelResponse

    monkeypatch.setattr(llm_client, "_REJECTED", {})
    entered, release = asyncio.Event(), asyncio.Event()
    sent = []
    first = LLMConfig(model="openai/queued", api_base="http://127.0.0.1:8081/v1", max_parallel=1)

    async def completion(**kwargs):
        sent.append(kwargs["api_base"])
        if len(sent) == 1:
            entered.set()
            await release.wait()
            raise RuntimeError("Unsupported parameter: temperature is not supported")
        return ModelResponse(choices=[{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"text":"ready"}'}}])

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    client = llm_client.LiteLLMClient(first)

    async def exercise():
        pending = asyncio.create_task(client.generate_structured_async(Reply, "Reply", "Hello"))
        await entered.wait()
        previous = None
        for index in range(transitions):
            client._use(first.model_copy(update={"api_base": f"http://127.0.0.1:{8082 + index}/v1"}))
            slots = client._slots_here()
            await slots.acquire()
            queued = asyncio.Event()
            acquire = slots.acquire

            async def observed_acquire(acquire=acquire, queued=queued):
                queued.set()
                return await acquire()

            monkeypatch.setattr(slots, "acquire", observed_acquire)
            if previous is None:
                release.set()
            else:
                previous.release()
            await queued.wait()
            previous = slots
        previous.release()
        assert (await pending).text == "ready"
        assert sent == [first.api_base, client.api_base]
        assert client.get_usage().requests == 2

    asyncio.run(asyncio.wait_for(exercise(), 5))


@pytest.mark.parametrize("when", ["queued", "running"])
def test_cancelled_migrating_request_releases_both_endpoints_slots(monkeypatch, when):
    from litellm import ModelResponse

    monkeypatch.setattr(llm_client, "_REJECTED", {})
    entered, release, migrated, finish = (asyncio.Event() for _ in range(4))
    first = LLMConfig(model="openai/cancelled", api_base="http://127.0.0.1:8081/v1", max_parallel=1)

    async def completion(**kwargs):
        if kwargs["api_base"] == first.api_base:
            entered.set()
            await release.wait()
            raise RuntimeError("Unsupported parameter: temperature is not supported")
        migrated.set()
        await finish.wait()
        return ModelResponse(choices=[{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"text":"ready"}'}}])

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    client = llm_client.LiteLLMClient(first)

    async def exercise():
        old_slots = client._slots_here()
        pending = asyncio.create_task(client.generate_structured_async(Reply, "Reply", "Hello"))
        await entered.wait()
        client._use(first.model_copy(update={"api_base": "http://127.0.0.1:8082/v1"}))
        slots = client._slots_here()
        if when == "queued":
            await slots.acquire()
            acquire = slots.acquire

            async def observed_acquire():
                migrated.set()
                return await acquire()

            monkeypatch.setattr(slots, "acquire", observed_acquire)
        release.set()
        await migrated.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        if when == "queued":
            slots.release()
        assert old_slots._value == slots._value == 1
        finish.set()
        assert (await client.generate_structured_async(Reply, "Reply", "Next")).text == "ready"

    asyncio.run(asyncio.wait_for(exercise(), 5))
