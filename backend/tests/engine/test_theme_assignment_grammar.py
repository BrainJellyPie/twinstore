"""Theme output grammars must cover the actual answers, without fabricating coverage."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.interview import ThemeCoding, code_themes
from store_emulator.engine.marketing.reading import Reason, code_reasons


@pytest.mark.parametrize("count", [4, 5, 17, 159, 160, 170])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_local_grammar_covers_every_kept_answer_and_preserves_group_counts(monkeypatch, tmp_path, count, mode):
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if mode == "json_schema":
            schema = body["response_format"]["json_schema"]["schema"]
        else:
            # Instructor's JSON mode puts the same schema in the final system message.
            message = next(m["content"] for m in reversed(body["messages"]) if m["role"] == "system")
            schema = json.JSONDecoder().raw_decode(message[message.index('{'):])[0]
        assignments = schema["properties"]["assignments"]
        # Completion at minItems is legal for a constrained local decoder. Before
        # this fix that minimum was zero, making every substantive answer Other.
        n = assignments.get("minItems", 0)
        payload = {"themes": ["Price", "Convenience"], "assignments": [i % 2 for i in range(n)]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/theme-count", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            reasons = [Reason(text=f"Answer {i}: {'Price' if i % 2 == 0 else 'Convenience'}", group="control" if i % 2 == 0 else "test")
                       for i in range(count)]
            reasons.insert(0, Reason(text="   ", group="ignored"))
            result = await code_reasons(client, "Why?", reasons)
            assert await code_reasons(client, "Why?", reasons) == result
            themes, coded, groups = result
            assert coded == min(count, 160) and groups == ["control", "test"]
            by_label = {theme.label: theme for theme in themes}
            assert set(by_label) == {"Price", "Convenience"}
            assert by_label["Price"].count == (coded + 1) // 2
            assert by_label["Convenience"].count == coded // 2
            assert by_label["Price"].by_group == {"control": (coded + 1) // 2, "test": 0}
            assert by_label["Convenience"].by_group == {"control": 0, "test": coded // 2}
            assert sum(t.share for t in themes) == pytest.approx(1, abs=1e-4)
            assert len(requests) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("assignments,expected", [([], [2, 2, 2]), ([0], [0, 2, 2]),
    ([0, 1, 99, 0], [0, 1, 2]), ([-1, 1, 0], [2, 1, 0])])
def test_non_enforcing_providers_keep_existing_explicit_other_fallback(assignments, expected):
    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            assert issubclass(schema, ThemeCoding)
            grammar = schema.model_json_schema()["properties"]["assignments"]
            assert grammar["minItems"] == grammar["maxItems"] == 3
            return schema(themes=["Price", "Convenience"], assignments=assignments)

    labels, codes = asyncio.run(code_themes(Model(), "Why?", ["a", "b", "c"]))
    assert labels == ["Price", "Convenience", "Other"] and codes == expected
