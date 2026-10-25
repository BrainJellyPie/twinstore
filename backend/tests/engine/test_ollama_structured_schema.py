"""Ollama's native format field must receive the same constraints as other local servers."""

import asyncio
import json
from collections import Counter
from typing import Literal

import httpx
import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field

from store_emulator.application import providers
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


class Answer(BaseModel):
    rack: Literal["section_0", "section_10"]
    products: list[str] = Field(min_length=1, max_length=2)
    interest: int = Field(ge=0, le=10)


def ollama_response(request, answer):
    if request.url.path.endswith("/api/show"):
        return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion", "vision"]})
    return httpx.Response(200, request=request, json={"model": "qwen3.5:2b", "created_at": "2026-10-25T00:00:00Z",
        "message": {"role": "assistant", "content": json.dumps(answer)}, "done": True, "done_reason": "stop",
        "prompt_eval_count": 10, "eval_count": 5})


@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image"])
@pytest.mark.parametrize("model", ["qwen3.5:2b", "local-model"])
def test_ollama_schema_reaches_native_text_and_image_calls(monkeypatch, tmp_path, mode, model):
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    requests = []

    def respond(request):
        if not request.url.path.endswith("/api/show"):
            # LiteLLM also asks for model metadata and may reuse a request
            # object; retain an immutable snapshot of generation requests.
            requests.append((request.url.path, json.loads(request.content)))
        return ollama_response(request, {"rack": "section_0", "products": ["tea"], "interest": 7})

    def send(self, request, *args, **kwargs): return respond(request)
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    config = providers.resolve_model(f"ollama:{model}", base=LLMConfig(cache_dir=str(tmp_path), seed=0), settings={})
    client = LiteLLMClient(config)
    for repeat in range(2):
        if mode == "sync":
            result = client.generate_structured(Answer, "Return JSON.", "Choose this shelf.")
        elif mode == "sync_image":
            result = client.generate_structured_with_image(Answer, "Return JSON.", "Choose this shelf.", "data:image/png;base64,AA==")
        elif mode == "async":
            result = asyncio.run(client.generate_structured_async(Answer, "Return JSON.", "Choose this shelf."))
        else:
            result = asyncio.run(client.generate_structured_with_image_async(Answer, "Return JSON.", "Choose this shelf.", "data:image/png;base64,AA=="))
        assert result.rack == "section_0" and result.interest == 7
        assert client.get_usage().cached_requests == repeat
    assert len(requests) == 1 and requests[0][0] == "/api/chat"
    body = requests[0][1]
    assert isinstance(body["format"], dict), "Only JSON syntax was requested; the model's field constraints were lost"
    validator = Draft202012Validator(body["format"])
    assert validator.is_valid(result.model_dump())
    for wrong in [{"rack": "section_999"}, {"products": []}, {"products": ["a", "b", "c"]}, {"interest": 11}]:
        assert not validator.is_valid({**result.model_dump(), **wrong})
    assert "response_format" not in body
    assert any(message.get("images") for message in body["messages"]) is ("image" in mode)


@pytest.mark.parametrize("ids", [["section_0"], ["section_0", "section_10"],
    ["진열대 🌿", "a/b", 'quote"', "back\\slash", "Case", "case", "__proto__"],
    [f"section_{i}" for i in range(13)]])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_automatic_starter_selection_transmits_its_dynamic_grammars(monkeypatch, tmp_path, ids, currency):
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    requests = []

    def respond(request):
        if request.url.path.endswith("/api/show"):
            return ollama_response(request, {})
        body = json.loads(request.content)
        context = json.loads(body["messages"][-1]["content"])
        if "racks" in context:
            answer = {"assignments": {rid: "home_coffee_tea" for rid in ids}}
        else:
            answer = {"selections": {key: [products[0]["sku"]] for key, products in context["categories"].items()}}
        requests.append((body, answer))
        return ollama_response(request, answer)

    def send(self, request, *args, **kwargs): return respond(request)
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    config = providers.resolve_model("ollama:qwen3.5:2b", base=LLMConfig(cache_dir=str(tmp_path), seed=0), settings={})
    client = LiteLLMClient(config)
    store = empty_store(currency)
    before = store.model_dump_json()
    racks = [StarterRack(id=rid, name="Shelf", type="shelf", available_slots=2) for rid in ids]

    async def exercise():
        first = await select_starter_products(client, store, racks, "동네 주민", allowed_categories={"home_coffee_tea"})
        assert Counter(row.rack_id for row in first) == Counter(ids)
        assert await select_starter_products(client, store, racks, "동네 주민", allowed_categories={"home_coffee_tea"}) == first

    asyncio.run(exercise())
    assert len(requests) == 2 and client.get_usage().cached_requests == 2
    for body, answer in requests:
        assert isinstance(body["format"], dict)
        validator = Draft202012Validator(body["format"])
        assert validator.is_valid(answer)
        invalid = json.loads(json.dumps(answer))
        if "assignments" in invalid:
            invalid["assignments"]["section_999"] = "home_coffee_tea"
        else:
            invalid["selections"]["home_coffee_tea"] = ["invented-sku"]
        assert not validator.is_valid(invalid)
    assert store.model_dump_json() == before


@pytest.mark.parametrize("endpoint,model", [
    ("http://127.0.0.1:11434", "qwen3.5:cloud"),
    ("http://127.0.0.1:11434", "qwen3.5:397b-cloud"),
    ("https://ollama.com", "cloud-alias"),
    ("https://OLLAMA.COM./", "cloud-alias"),
])
def test_ollama_cloud_keeps_its_supported_json_mode(monkeypatch, endpoint, model):
    requests = []

    def respond(request):
        if request.url.path.endswith("/api/show"):
            return ollama_response(request, {})
        body = json.loads(request.content)
        requests.append(body)
        if isinstance(body.get("format"), dict):
            return httpx.Response(400, request=request, json={"error": "Cloud does not support structured outputs"})
        return ollama_response(request, {"rack": "section_0", "products": ["tea"], "interest": 7})

    def send(self, request, *args, **kwargs): return respond(request)
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    config = providers.resolve_model(f"ollama:{model}", settings={ProviderKind.OLLAMA:
        providers.ProviderSettings(kind=ProviderKind.OLLAMA, api_base=endpoint)})
    assert config.structured_output == "json"
    result = asyncio.run(LiteLLMClient(config).generate_structured_async(Answer, "Return JSON.", "Choose this shelf."))
    assert result.rack == "section_0" and len(requests) == 1 and requests[0]["format"] == "json"
