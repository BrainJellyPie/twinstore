"""Trip explanations and follow-ups must retain the shopper's individual purchase evidence."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.interview import InterviewMessage, Journey, JourneyStep
from store_emulator.domain.types import Action
from store_emulator.engine import llm_client
from store_emulator.engine.interview import ask_shopper, suggest_follow_ups
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("operation", ["answer", "follow_up"])
@pytest.mark.parametrize("purpose", ["weekly groceries", ""])
@pytest.mark.parametrize("field,value", [
    ("intent", "Find caffeine-free tea for tonight's dinner."),
    ("preferred_categories", ["caffeine-free tea", "fresh fruit"]),
    ("intent", ""), ("preferred_categories", []),
])
def test_personal_evidence_reaches_both_interview_requests_and_cache(monkeypatch, tmp_path, mode, operation, purpose, field, value):
    store, _ = fixture()
    persona = _persona().model_copy(update={"purpose": purpose})
    journey = Journey(run_id="run-personal-evidence", persona=persona, day=1, arrival_time="12:00:00",
        leave_time="12:01:00", engine_type="rule_based", currency="USD", total_spent=100, units=1,
        steps=[JourneyStep(index=1, time="12:00:10", elapsed_sec=10, action=Action.BUY,
                           product_name="Tea", product_sku="seen", price=100, quantity=1)], path=[])
    changed = journey.model_copy(update={"persona": persona.model_copy(update={field: value})})
    history = [InterviewMessage(role="interviewer", text="What brought you here?"),
               InterviewMessage(role="shopper", text="I needed a drink.")]
    original, calls = llm_client.litellm.acompletion, []
    marker = value[0] if isinstance(value, list) and value else value

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = ({"answer": "I chose the tea.", "steps": [1, 999]} if operation == "answer"
                   else {"questions": ["What mattered when choosing that tea?"]})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/interview-personal-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run(trip):
                if operation == "answer":
                    reply = await ask_shopper(client, trip, store, history, "Why that tea?")
                    assert reply.steps == [1]
                    return reply.model_dump()
                return await suggest_follow_ups(client, trip, store, history)

            initial = await run(journey)
            assert await run(journey) == initial and len(calls) == 1
            fresh = await run(changed)
            assert len(calls) == 2, "Changed personal evidence reused the old interview response"
            user = calls[-1]["messages"][1]["content"]
            if marker:
                assert marker in user
            assert "I needed a drink." in user
            assert "Tea ×1 for $1.00" in user and "[1]" in user
            if purpose:
                assert purpose in user
            assert await run(changed) == fresh and len(calls) == 2

    asyncio.run(exercise())
