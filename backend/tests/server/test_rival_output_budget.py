"""A full shelf's model-confirmed matches must fit beyond a short narration budget."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application import shelf_lab
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import read_setup, setup_path
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from tests.engine.test_rival_comparison_boundaries import pair
from tests.server.test_shelf_lab_start_snapshot import CID, lab
from tests.server.test_simulation_setup_races import PID, SID, layout
from tests.server.test_town_save_lifecycle import neighborhood


# Compact / indented JSON, measured with the Qwen3.5 tokenizer without running a model.
TOKENS = {("english", 8): (252, 372), ("english", 30): (934, 1362), ("english", 80): (2484, 3612),
          ("korean", 8): (300, 420), ("korean", 30): (1114, 1542), ("korean", 80): (2964, 4092)}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("language", ["english", "korean"])
@pytest.mark.parametrize("count", [8, 30, 80])
@pytest.mark.parametrize("pretty", [False, True])
def test_complete_rival_shelf_matches_reach_comparison_apply_and_cache(
    neighborhood, lab, monkeypatch, tmp_path, mode, language, count, pretty,
):
    client, town = neighborhood
    _, _, _, folder = lab
    pairs = [{"rival": (f"Twin Original Tea {i:02d} 500ml" if language == "english" else f"트윈 오리지널 녹차 {i:02d} 500ml"),
              "ours": (f"Twin Original Tea {i:02d} 500 ml" if language == "english" else f"트윈 오리지널 녹차 {i:02d} 500 ml")}
             for i in range(count)]
    store, capture = pair(our_price=200, rival_price=100)
    rack, item = store.racks[0], capture.items[0]
    store.grid_size = (20, 20)
    store.racks = [rack.model_copy(deep=True, update={"id": f"rack_{i}", "position": (i % 20, i // 20),
        "slots": [rack.slots[0].model_copy(update={"items": [SlotItem(sku=f"sku_{i}", name=row["ours"], price=200)]})]})
        for i, row in enumerate(pairs)]
    capture.items = [item.model_copy(update={"id": f"item_{i}", "name": row["rival"]}) for i, row in enumerate(pairs)]
    capture.currency = "USD"
    data = read_setup(PID, SID)
    write_json(setup_path(PID, SID), {**data, "store": store.model_dump(mode="json")})
    write_json(folder / "result.json", capture.model_dump(mode="json"))
    source = setup_path(PID, SID).read_bytes(), (folder / "result.json").read_bytes()
    payload = {"pairs": pairs}
    content = json.dumps(payload, ensure_ascii=False, indent=2) if pretty else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    required = TOKENS[language, count][int(pretty)]
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        truncated = body["max_tokens"] < required
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if truncated else "stop",
                "message": {"role": "assistant", "content": content[:32] if truncated else content}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    def model(requested, config):
        return llm_client.LiteLLMClient(config.model_copy(update={"model": "openai/rival-budget",
            "api_base": "http://127.0.0.1:8081/v1", "structured_output": mode, "seed": 0,
            "cache_dir": str(tmp_path / "cache")}))

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    monkeypatch.setattr(shelf_lab, "assistive_client", model)
    for _ in range(2):
        response = client.post(f"/api/projects/{PID}/captures/{CID}/rival", json={
            "setup_id": SID, "venue_id": "cafe", "apply": True, "match_with_model": True,
        })
        assert response.status_code == 200, response.text
        report = response.json()
        assert not report["match_note"]
        assert report["model_matches"] == {row["rival"]: row["ours"] for row in pairs}
        assert report["comparison"]["matched"] == count and len(report["comparison"]["prices"]) == count
        assert report["comparison"]["price_index"] == pytest.approx(.5)
        assert report["comparison"]["suggested_pull_factor"] == 1.5
        assert report["attractiveness"] == round(town.get_venue("cafe").attractiveness * 1.5, 3)
        assert len(requests) == 1 and required <= requests[0]["max_tokens"] <= 6144
        assert (setup_path(PID, SID).read_bytes(), (folder / "result.json").read_bytes()) == source
