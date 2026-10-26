"""The transmitted grammar must require the fields each proposed operation uses."""

import asyncio
import copy
import json

import httpx
import pytest
from jsonschema import Draft202012Validator

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import design_experiment
from tests.engine.test_layout_applied_changes import fixture


CHANGES = [
    {"kind": "price", "product": "Tea", "price": 0},
    {"kind": "discount", "product": "Tea", "percent": -100},
    {"kind": "promo", "product": "Tea", "promo": "1+1"},
    {"kind": "move", "product": "Tea", "shelf": "Destination"},
    {"kind": "package", "product": "Tea", "package": "New pack"},
    {"kind": "category_price", "category": "Drinks", "percent": -10},
]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("change", CHANGES, ids=lambda change: change["kind"])
def test_real_draft_adapter_sends_operation_specific_constraints_and_reuses_cache(monkeypatch, tmp_path, mode, change):
    store, _ = fixture("valid")
    before = store.model_dump_json()
    requests = []
    payload = {"name": "Tea test", "variants": [{"name": "Changed tea", "changes": [change]}]}

    async def send(self, request, *args, **kwargs):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion",
            "created": 0, "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    client = LiteLLMClient(LLMConfig(model="openai/operation-schema", api_base="http://127.0.0.1:8081/v1",
        api_key="offline", structured_output=mode, cache_dir=str(tmp_path), seed=0))

    async def exercise():
        first = await design_experiment(client, "Compare Tea variants", store, "USD", [("New pack", "pack")])
        assert first.variants[0].changes[0].kind == change["kind"]
        assert not first.warnings
        assert await design_experiment(client, "Compare Tea variants", store, "USD", [("New pack", "pack")]) == first

    asyncio.run(exercise())
    assert len(requests) == 1 and client.get_usage().cached_requests == 1
    assert store.model_dump_json() == before
    body = requests[0]
    if mode == "json_schema":
        schema = body["response_format"]["json_schema"]["schema"]
    else:
        system = next(message["content"] for message in body["messages"] if message["role"] == "system")
        schema = json.loads(system.split("matching this schema:", 1)[1].split(
            "Return a valid JSON instance, not the schema definition.", 1)[0].strip())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    assert validator.is_valid(payload)

    def accepts(candidate):
        draft = copy.deepcopy(payload)
        draft["variants"][0]["changes"][0] = candidate
        return validator.is_valid(draft)

    for field in change:
        assert not accepts({key: value for key, value in change.items() if key != field}), field
        assert not accepts({**change, field: None}), field
        if isinstance(change[field], str):
            assert not accepts({**change, field: ""}), field
    assert not accepts({**change, "unrecognized": "ignored"})
    if change["kind"] != "category_price":
        assert not accepts({**change, "category": "Tea"})
        assert not accepts({key: value for key, value in {**change, "category": "Tea"}.items() if key != "product"})
    else:
        assert not accepts({**change, "product": "Tea"})
        assert accepts({**change, "percent": 0})
        assert not accepts({**change, "percent": -101})
        assert not accepts({**change, "percent": 301})
    if change["kind"] == "price":
        assert accepts({**change, "price": 1.99})
        assert not accepts({**change, "price": -0.01})
        assert not accepts({**change, "price": "1.99"})
    elif change["kind"] == "discount":
        assert accepts({**change, "percent": -0.5})
        for invalid in [-101, 0, 20, "-20"]:
            assert not accepts({**change, "percent": invalid})
    elif change["kind"] == "move":
        for level in [1, 3, 4]:
            assert accepts({**change, "level": level})
        for level in [0, 5, 2.5, None]:
            assert not accepts({**change, "level": level})
    elif change["kind"] == "promo":
        assert not accepts({**change, "promo": "x" * 25})
