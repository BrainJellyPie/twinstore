"""Missing or contradictory measurements are failures, not synthetic no-choice votes."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.shelf_lab.sim2real import TwinViews, glance_panel, summarize
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance, shelf_glance_model
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_shelf_panel_boundaries import shelf


INVALID = [{}, {"product": "Banana", "number": 2}, {"interest": 8},
           {"product": None, "number": 0, "interest": 10}, {"product": " \t", "number": 0, "interest": 1},
           {"product": "", "number": 0, "interest": 8}, {"product": "Ghost product", "interest": 8},
           {"number": 9999, "interest": 8}]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("payload", INVALID)
@pytest.mark.parametrize("routing", ["single", "vote"])
@pytest.mark.parametrize("legacy_cache", [False, True])
def test_invalid_interest_cannot_be_cached_or_lower_a_valid_vote(monkeypatch, tmp_path, collision_store, shelf,
                                                              mode, payload, routing, legacy_cache):
    rack, view = shelf
    calls, phase = [], "prime" if legacy_cache else "missing"
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        good = body["model"].endswith("good")
        answer = {"product": "Banana", "number": 2, "interest": 8} if good or phase == "prime" else (
            payload if phase == "missing" else {"number": 0, "interest": 0})
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
            args = (view, "Choose one product", _context(collision_store, _persona()), rack, "N")
            if legacy_cache:
                assert (await engine._ask(*args))[0].interest == 8
                path = next((tmp_path / "missing").rglob("*.json"))
                cached = json.loads(path.read_text())
                cached["result"] = payload
                path.write_text(json.dumps(cached))
                phase = "missing"
            first = await engine._ask(*args)
            if routing == "single":
                assert first[0] is None and first[-1]
                if "interest" not in payload:
                    assert "interest" in first[-1]
            else:
                assert first[0].interest == 8 and first[2] == 1
                assert any(member == "missing" and interest == -1 for member, _, interest in first[3])
            if not legacy_cache:
                assert not list((tmp_path / "missing").rglob("*.json"))
            phase = "explicit-zero"
            second = await engine._ask(*args)
            assert second[0] is not None and not second[-1]
            assert second[0].interest == (0 if routing == "single" else 4)
            before = len(calls)
            assert await engine._ask(*args) == second and len(calls) == before
            assert len([call for call in calls if call["model"] == "missing"]) == 2 + int(legacy_cache)

    asyncio.run(exercise())


@pytest.mark.parametrize("payload", INVALID)
def test_photo_comparison_excludes_invalid_interest_but_counts_explicit_zero(shelf, payload):
    rack, view = shelf
    conditions = ["render", "photo", "photo_raw"]
    views = TwinViews(rack, view.face, {condition: view for condition in conditions}, {"A": "Apple", "B": "Banana"})

    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            return schema.model_validate(payload)

    def panel():
        return asyncio.run(glance_panel(Model(), views, [_persona()], conditions=conditions,
            cue_sampler=lambda rng: BehaviorCue(), patterns=BEHAVIOR_PATTERNS))

    answers = panel()
    assert all(answer.error and answer.resolved_by == "error" for answer in answers)
    stats, agreement = summarize(answers, conditions)
    assert all(stat.answers == 0 and stat.errors == 1 for stat in stats) and agreement == []
    payload = {"number": 0, "interest": 0}
    stats, agreement = summarize(panel(), conditions)
    assert all(stat.answers == 1 and stat.errors == 0 and stat.none_rate == 1 for stat in stats)
    assert all(pair.pairs == 1 and pair.same_pick == 1 for pair in agreement)


def test_model_grammar_requires_interest_without_changing_internal_defaults(shelf):
    _, view = shelf
    assert ShelfGlance().interest == 0
    for numbered in [False, True]:
        schema = shelf_glance_model(view, numbered=numbered).model_json_schema()
        assert "interest" in schema.get("required", [])
        assert schema["properties"]["interest"]["minimum"] == 0
        assert schema["properties"]["interest"]["maximum"] == 10


@pytest.mark.parametrize("payload", [
    {"product": "Banana", "interest": 8}, {"number": 2, "interest": 8},
    {"product": "Banana", "number": 9999, "interest": 8},
    {"product": "Ghost product", "number": 2, "interest": 8}, {"interest": 0},
])
def test_identifiable_choices_and_zero_interest_keep_existing_resolution(shelf, payload):
    _, view = shelf
    glance = shelf_glance_model(view).model_validate(payload)
    assert glance.interest == payload["interest"]
