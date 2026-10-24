"""An omitted entry decision must not become a synthetic yes vote."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import EntryDecision, PLAN_ITEMS_LIMIT, entry_decision_model
from tests.engine.test_llm_engine_offline import _context, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("payload", [{}, {"mission": "consider a visit", "items": []}])
@pytest.mark.parametrize("routing", ["single", "vote"])
@pytest.mark.parametrize("image", [False, True])
@pytest.mark.parametrize("legacy_cache", [False, True])
def test_missing_entry_cannot_be_cached_or_overrule_a_walkout(monkeypatch, tmp_path, collision_store,
                                                           mode, payload, routing, image, legacy_cache):
    calls, phase = [], "prime" if legacy_cache else "missing"
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        good = body["model"].endswith("good")
        answer = {"enter": False} if good or phase == "explicit" else (
            {"enter": True} if phase == "prime" else payload)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)

            def client(name):
                return llm_client.LiteLLMClient(LLMConfig(model=f"openai/{name}", api_base="http://127.0.0.1:8081/v1",
                    structured_output=mode, cache_dir=str(tmp_path / name)))

            bad = client("missing")
            model = bad if routing == "single" else EnsembleLLMClient([
                ("missing", 1, bad), ("good", 1, client("good"))], mode="vote")
            engine = VLMGlanceEngine(model, AStarPathFinder(), SimulationConfig())
            args = (entry_decision_model(3), "Plan the visit", "Enter or leave", "data:image/png;base64,AA==" if image else None,
                    _context(collision_store, _persona()))
            if legacy_cache:
                assert (await engine._ask_plan(*args))[0].enter is True
                path = next((tmp_path / "missing").rglob("*.json"))
                cached = json.loads(path.read_text())
                cached["result"].pop("enter")
                path.write_text(json.dumps(cached))
                phase = "missing"
            first = await engine._ask_plan(*args)
            if routing == "single":
                assert first[0] is None and "enter" in first[-1]
            else:
                assert first[0].enter is False and first[2] == 1
            if not legacy_cache:
                assert not list((tmp_path / "missing").rglob("*.json"))
            phase = "explicit"
            second = await engine._ask_plan(*args)
            assert second[0] is not None and second[0].enter is False and not second[-1]
            before = len(calls)
            cached = await engine._ask_plan(*args)
            assert cached[0].model_dump() == second[0].model_dump() and cached[1:] == second[1:]
            assert len(calls) == before
            assert len([call for call in calls if call["model"] == "missing"]) == 2 + int(legacy_cache)

    asyncio.run(exercise())


@pytest.mark.parametrize("cap", [0, 1, 3, PLAN_ITEMS_LIMIT, PLAN_ITEMS_LIMIT + 1])
def test_entry_is_required_at_every_model_item_limit_but_internal_defaults_remain(cap):
    schema = entry_decision_model(cap)
    assert "enter" in schema.model_json_schema().get("required", [])
    assert schema.model_json_schema()["properties"]["items"]["maxItems"] == min(cap, PLAN_ITEMS_LIMIT)
    with pytest.raises(ValidationError):
        schema.model_validate_json('{}', strict=True)
    for enter in [False, True]:
        assert schema.model_validate_json(json.dumps({"enter": enter}), strict=True).enter is enter
    assert EntryDecision().enter is True


def test_run_does_not_claim_an_empty_first_response_is_a_vision_plan(collision_store):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({})

    config = SimulationConfig()
    config.engines.vlm_glance.entrance_image = False
    config.engines.vlm_glance.max_glances = 0
    engine = VLMGlanceEngine(Model(), AStarPathFinder(), config)
    with pytest.raises(RuntimeError, match="vision model did not answer"):
        asyncio.run(engine.decide_actions(_context(collision_store, _persona())))
    assert not engine.plan_log
