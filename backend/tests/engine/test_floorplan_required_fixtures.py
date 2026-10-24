"""An omitted model fixture list cannot silently import an empty store."""

import io
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application import floorplan
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, setup_dir, setup_path
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.store import Store
from store_emulator.engine import llm_client
from store_emulator.engine.floorplan.read import _VLMPlan
from tests.engine.test_floorplan import sketch
from tests.engine.test_floorplan_model_geometry import GOOD


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("reader", ["auto", "vlm"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache", "empty"])
def test_fixture_omissions_repair_or_fall_back_before_importing(monkeypatch, tmp_path, mode, reader, outcome):
    monkeypatch.chdir(tmp_path)
    pid = "proj_requiredfixtures"
    write_json(metadata_path(pid), {"name": "Corner Store", "currency": "USD"})
    cache = tmp_path / "cache"
    config = LLMConfig(model="openai/local-plan", api_base="http://127.0.0.1:8081/v1",
        structured_output=mode, cache_dir=str(cache), seed=0)
    monkeypatch.setattr(floorplan, "capture_llm_config", lambda *args: config)
    original, calls = llm_client.litellm.acompletion, []
    phase = "prime" if outcome == "legacy_cache" else "invalid"

    def respond(request):
        body = json.loads(request.content)
        bad = phase == "invalid" and not (outcome == "corrected" and calls)
        payload = {k: v for k, v in GOOD.items() if not (k == "fixtures" and bad)}
        if outcome == "empty":
            payload["fixtures"] = []
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    with sketch() as photo:
        output = io.BytesIO()
        photo.save(output, format="PNG")
        png = output.getvalue()

    def read():
        return floorplan.import_floor_plan(pid, png, "plan.png", reader=reader, model="local", name="Plan",
                                           config=SimulationConfig())

    if outcome == "legacy_cache":
        read()
        paths = list(cache.rglob("*.json"))
        assert len(paths) == 1
        data = json.loads(paths[0].read_text())
        del data["result"]["fixtures"]
        paths[0].write_text(json.dumps(data))
        phase = "invalid"
    if outcome in {"repeated", "legacy_cache"}:
        before = set(setup_dir(pid).glob("*.json"))
        if reader == "vlm":
            with pytest.raises(AppError, match="could not read the plan") as caught:
                read()
            assert caught.value.status_code == 502
            assert set(setup_dir(pid).glob("*.json")) == before
        else:
            fallback = read()
            assert fallback.reading.reader == "classic" and fallback.racks > 0
            assert any("vision model unavailable" in note for note in fallback.notes)
        assert len(calls) == (3 if outcome == "legacy_cache" else 2)
        phase = "complete"
    result = read()
    assert result.reading.reader == config.model
    stored = Store.model_validate(read_json(setup_path(pid, result.setup_id))["store"])
    if outcome == "empty":
        assert not result.reading.fixtures and result.racks == 0 and not any(r.slots for r in stored.racks)
    else:
        assert len(result.reading.fixtures) == 3 and result.racks > 0 and any(r.slots for r in stored.racks)
    before = len(calls)
    repeated = read()
    assert repeated.reading == result.reading and repeated.racks == result.racks and len(calls) == before
    if outcome == "corrected":
        assert len(calls) == 2
    for path in cache.rglob("*.json"):
        assert "fixtures" in json.loads(path.read_text())["result"]


def test_model_schema_requires_an_explicit_fixture_list_but_keeps_empty_plans_valid():
    schema = _VLMPlan.model_json_schema()
    assert "fixtures" in schema["required"]
    assert _VLMPlan.model_validate({"outline": [0, 0, 1000, 1000], "fixtures": []}).fixtures == []
