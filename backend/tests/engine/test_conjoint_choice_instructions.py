"""The no-purchase setting must agree in the prompt, wire schema and recorded choices."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ConjointAttribute
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.conjoint import conjoint_panel
from tests.engine.test_llm_engine_offline import _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("options", [2, 3, 4])
@pytest.mark.parametrize("none_option", [False, True])
def test_choice_instructions_agree_with_requested_options_and_cache(monkeypatch, tmp_path, mode, options, none_option):
    calls = []
    original = llm_client.litellm.acompletion
    labels = "ABCD"[:options]
    answer = {"task_1": labels[-1], "task_2": "none" if none_option else "A"}

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/conjoint-choice-instructions",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            args = (client, [_persona()], [ConjointAttribute(name="Style", levels=["Regular", "Decaf"])], [149, 199])
            settings = dict(product="Tea", tasks=2, options=options, none_option=none_option, seed=42)
            result = await conjoint_panel(*args, **settings)
            assert len(result) == 1 and not result[0].error
            assert [task.choice for task in result[0].tasks] == [options - 1, None if none_option else 0]
            assert await conjoint_panel(*args, **settings) == result
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            body = calls[0]
            system = next(m["content"] for m in body["messages"] if m["role"] == "system")
            user = next(m["content"] for m in body["messages"] if m["role"] == "user")
            assert ('or "none" if' in system) is none_option, "System instruction contradicts the no-purchase setting"
            assert ("none: buy none of these" in user) is none_option
            if mode == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                assert schema["properties"]["task_1"]["enum"] == [*labels, *(["none"] if none_option else [])]
            # The other setting must get a fresh request, not reuse the previous choice.
            answer["task_2"] = "A" if none_option else "none"
            other = await conjoint_panel(*args, **{**settings, "none_option": not none_option})
            assert not other[0].error and len(calls) == 2
            assert other[0].tasks[1].choice == (0 if none_option else None)

    asyncio.run(exercise())


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_disallowed_none_is_a_failed_response_not_an_invented_purchase(monkeypatch, tmp_path, mode):
    from tests.engine.test_local_thinking_json import exercise
    from store_emulator.engine.marketing.conjoint import choice_model

    # Exercise the real parser even for a provider that ignores its transmitted grammar.
    monkeypatch.setattr("tests.engine.test_local_thinking_json.Reply", choice_model(1, 2, False))
    asyncio.run(exercise(monkeypatch, tmp_path, mode, "async", '{"task_1":"none"}', expect_error=True))
