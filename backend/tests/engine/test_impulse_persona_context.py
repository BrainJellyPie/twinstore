"""An impulse shopper must retain individual needs beyond coarse cohort labels."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["description", "intent", "both"])
def test_changed_personal_needs_reach_impulse_prompt_and_cannot_reuse_old_answer(monkeypatch, tmp_path, mode, field):
    store, intent = fixture()
    original, calls, impulse_prompts = llm_client.litellm.acompletion, [], []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "## 행동 패턴 목록" in system:
            payload = {"pattern_id": "exploratory"}
        elif "세렌디피티" in system:
            impulse_prompts.append(user)
            payload = {"reasoning": f"Personal needs review {len(impulse_prompts)}", "actions": []}
        else:
            payload = intent.model_dump(mode="json")
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/impulse-persona-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig())
            expected = []
            for revision in range(2):
                values = dict(description=f"Individual description {revision}: prefers decaf tea.",
                              intent=f"Individual intent {revision}: needs an unsweetened drink.")
                person = _persona()
                for key, value in values.items():
                    if field in [key, "both"]:
                        setattr(person, key, value)
                context = _context(store, person)
                expected.append((person.description, person.intent))
                decision = await engine.decide_actions(context)
                cached = await engine.decide_actions(context)
                assert cached.model_dump() == decision.model_dump()
                assert decision.trace["stage3"]["reasoning"] == f"Personal needs review {revision + 1}"
            assert len(calls) == 6 and len(impulse_prompts) == 2
            assert impulse_prompts[0] != impulse_prompts[1]
            for prompt, (description, purpose) in zip(impulse_prompts, expected, strict=True):
                assert description in prompt and purpose in prompt

    asyncio.run(exercise())
