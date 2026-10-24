"""Changing a shopper's personal needs must reach each study and invalidate its response cache."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ConjointAttribute
from store_emulator.domain.types import Face
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.conjoint import conjoint_panel
from store_emulator.engine.marketing.shelf_test import shelf_panel
from store_emulator.engine.marketing.survey import survey_panel
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("study", ["survey", "conjoint", "shelf"])
@pytest.mark.parametrize("field,value", [
    ("intent", "Buy caffeine-free tea for tonight's dinner."),
    ("behavior_tendency", "Reject caffeine after lunch even when it is discounted."),
    ("preferred_categories", ["caffeine-free tea", "fresh fruit"]),
    ("intent", ""), ("behavior_tendency", ""), ("preferred_categories", []),
])
def test_changed_personal_context_reaches_study_requests_and_cache(monkeypatch, tmp_path, mode, study, field, value):
    original = llm_client.litellm.acompletion
    calls = []
    persona = _persona().model_copy(update={"behavior_tendency": "Always compares unit prices."})
    marker = value[0] if isinstance(value, list) and value else value
    revised = persona.model_copy(update={field: value})

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if study == "survey":
            answer = {"purchase_intent_A": 4}
        elif study == "conjoint":
            answer = {"task_1": "A"}
        else:
            answer = {"pick": 0, "noticed": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/study-personal-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run(person):
                if study == "survey":
                    return await survey_panel(client, [person], Image.new("RGB", (40, 40), "white"), ["purchase_intent"], 1)
                if study == "conjoint":
                    return await conjoint_panel(client, [person], [ConjointAttribute(name="Style", levels=["Regular", "Decaf"])],
                                                [100, 200], product="Tea", tasks=1, options=2)
                store, _ = fixture()
                return await shelf_panel(client, [person], store.racks[0], store.racks[0], Face.S)

            initial = await run(persona)
            assert not any(answer.error for answer in initial)
            per_run = 2 if study == "shelf" else 1
            assert len(calls) == per_run
            assert await run(persona) == initial
            assert len(calls) == per_run
            fresh = await run(revised)
            assert not any(answer.error for answer in fresh)
            assert len(calls) == per_run * 2, "Changed shopper evidence incorrectly reused the old study answer"
            if marker:
                assert all(marker in json.dumps(body["messages"], ensure_ascii=False) for body in calls[per_run:])
            assert await run(revised) == fresh
            assert len(calls) == per_run * 2

    asyncio.run(exercise())
