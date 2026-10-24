"""A local glance grammar permits only badges actually printed in the current view."""

import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import resolve, shelf_glance_model
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_shelf_panel_boundaries import shelf


@pytest.mark.parametrize("marks", [(1, 2), (2, 7), ()])
@pytest.mark.parametrize("routing", ["single", "mixture", "vote"])
@pytest.mark.parametrize("truncated", [False, True])
def test_http_glance_uses_the_current_badges_and_caches_valid_choices(monkeypatch, tmp_path, collision_store, shelf, marks, routing, truncated):
    rack, view = shelf
    view = replace(view, items=tuple(replace(item, mark=mark) for item, mark in zip(view.items, marks)))
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        schema = body["response_format"]["json_schema"]["schema"]
        assert schema["properties"]["number"]["enum"] == [0, *marks]
        finish = "length" if truncated and routing != "vote" and len(calls) == 1 else "stop"
        answer = {"product": "", "number": marks[-1] if marks else 0, "interest": 7 if marks else 0}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/badge-grammar", api_base="http://127.0.0.1:8081/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), max_tokens=160))
            model = client if routing == "single" else EnsembleLLMClient([("first", 1, client), ("second", 1, client)], mode=routing)
            engine = VLMGlanceEngine(model, AStarPathFinder(), SimulationConfig())
            args = (view, "Choose one product", _context(collision_store, _persona()), rack, "N")
            first = await engine._ask(*args)
            assert not first[-1] and first[0] is not None
            selected, how = resolve(view, first[0])
            assert (selected.item.sku if selected else "") == (view.items[-1].item.sku if marks else "")
            before = len(calls)
            second = await engine._ask(*args)
            assert first == second
            # A truncation recovery changes max_tokens, so the initial smaller
            # request is retried on the next glance; only successful keys cache.
            assert len(calls) <= before + int(truncated and routing != "vote")
            assert how in {"number", "name", "none"}

    asyncio.run(exercise())


@pytest.mark.parametrize("numbered", [False, True])
@pytest.mark.parametrize("product,number,expected", [("Apple", 999, "A"), ("Apple", 2, "A"), ("", 2, "B"),
                                                    ("", 0, ""), ("Invented product", 999, "")])
def test_non_enforcing_providers_keep_existing_name_and_badge_resolution(shelf, numbered, product, number, expected):
    _, view = shelf
    schema = shelf_glance_model(view, numbered=numbered)
    assert schema.model_json_schema()["properties"]["number"]["enum"] == ([0, 1, 2] if numbered else [0])
    glance = schema.model_validate_json(json.dumps({"product": product, "number": number, "interest": 7}), strict=True)
    selected, _ = resolve(view, glance)
    assert (selected.item.sku if selected else "") == expected


@pytest.mark.parametrize("raw_numeric_only", [False, True])
def test_photo_panel_uses_zero_only_for_unmarked_photos(shelf, raw_numeric_only):
    from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
    from store_emulator.domain.behavior import BehaviorCue
    from store_emulator.engine.shelf_lab.sim2real import TwinViews, glance_panel

    rack, view = shelf
    conditions = ["render", "photo", "photo_raw"]
    views = TwinViews(rack, view.face, {c: view for c in conditions}, {m.item.sku: m.item.name for m in view.items})

    class Model:
        calls = 0

        async def generate_structured_with_image_async(self, schema, system, *args, **kwargs):
            self.calls += 1
            raw = "- number: 0" in system
            assert schema.model_json_schema()["properties"]["number"]["enum"] == ([0] if raw else [0, 1, 2])
            return schema.model_validate({"number": 2, "product": "" if raw_numeric_only else "Banana", "interest": 8})

    model = Model()
    answers = asyncio.run(glance_panel(model, views, [_persona()], conditions=conditions,
        cue_sampler=lambda rng: BehaviorCue(), patterns=BEHAVIOR_PATTERNS))
    assert model.calls == 3
    assert [answer.sku for answer in answers] == ["B", "B", "" if raw_numeric_only else "B"]
    assert [bool(answer.error) for answer in answers] == [False, False, raw_numeric_only]
