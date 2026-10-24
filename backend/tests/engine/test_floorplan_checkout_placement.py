"""Every imported entrance position keeps a reachable checkout and payable trip."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.types import Action, FACE_OFFSETS, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.floorplan import plan_to_store, vlm_read
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("door", [(0, 500), (1000, 500), (500, 0), (500, 1000), (0, 0), (0, 1000), (1000, 0), (1000, 1000)])
@pytest.mark.parametrize("counter", ["missing", "colliding", "fixed"])
def test_http_floorplan_retains_checkout_at_all_entrance_edges(monkeypatch, tmp_path, mode, door, counter):
    fixtures = [{"kind": "gondola", "box": [400, 400, 600, 500], "label": "snacks"},
                {"kind": "entrance", "box": [*door, *door]}]
    if counter == "fixed":
        fixtures.append({"kind": "counter", "box": [750, 750, 790, 790]})
    elif counter == "colliding":
        x, y = (min(960, value) for value in door)
        fixtures.append({"kind": "counter", "box": [x, y, x + 40, y + 40]})
    payload = {"outline": [0, 0, 1000, 1000], "width_m": 20, "depth_m": 20, "fixtures": fixtures}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/floorplan-checkout-placement", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (40, 40)) as photo:
                reading = await vlm_read(client, photo)
                store, notes = plan_to_store(reading)
                assert len(store.counters) == 1
                till, entrance = store.counters[0], store.entrances[0]
                assert till.position != entrance.position
                assert not [i for i in validate(store) if i.severity == "error" or i.code in {"no_counter", "blocked_slot"}]
                if counter == "fixed":
                    assert till.position == (12, 12)
                if counter == "colliding":
                    assert any("counter" in note and "entrance" in note for note in notes)
                rack = store.product_racks[0]
                slot = rack.slots[0]
                item = slot.items[0]
                dx, dy = FACE_OFFSETS[slot.face]
                stance = rack.position[0] + dx, rack.position[1] + dy
                grid = store.walkable_grid()
                payment = next((x, y) for x, y in sorted(till.service_access_tiles(store.grid_size)) if grid[y][x])
                decision = EngineDecision(engine_type="vlm_glance", actions=[
                    CustomerAction(nav="path", target=entrance.position, action=Action.ENTER),
                    CustomerAction(nav="path", target=stance, face=slot.face, action=Action.BUY, product_sku=item.sku),
                    CustomerAction(nav="path", target=payment, action=Action.PAY),
                    CustomerAction(nav="leave", action=Action.EXIT),
                ])
                result = execute_decision(store, "p", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
                assert len(result.purchases) == 1 and result.total_spent == item.price
                assert sum(event.action == Action.PAY for event in result.timeline) == 1
                assert result.timeline[-1].action == Action.EXIT
                repeated, repeated_notes = plan_to_store(await vlm_read(client, photo))
                assert repeated.model_dump() == store.model_dump() and repeated_notes == notes
                assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())
