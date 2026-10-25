"""Real small-model replies may contain valid choices plus echoed schema metadata."""

import asyncio
import json

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client
from store_emulator.engine.layout_gen.catalog import CATALOG
from store_emulator.engine.starter_selection import CategorySelection, _small_choices, select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("annotations", [
    {"title": "Choices", "type": "array"},
    {"title": "Choices", "type": "array", "minItems": 1, "maxItems": 8},
    {"explanation": "These are the listed products", "invented": ["@P999"]},
])
def test_valid_choices_survive_advisory_fields_without_caching_them(monkeypatch, tmp_path, mode, annotations):
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if mode == "json_schema":
            assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
        answer = {"choices": ["@P1", "@P2"], **annotations}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/schema-echo", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))
            for _ in range(2):
                chosen = await _small_choices(client, "Choose listed products", {}, {"@P1", "@P2"}, 1, 2, unique=True)
                assert chosen == ["@P1", "@P2"]
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            cache = list(tmp_path.glob("*/*.json"))
            assert len(cache) == 1
            assert json.loads(cache[0].read_text())["result"] == {"choices": ["@P1", "@P2"]}

    asyncio.run(exercise())


@pytest.mark.parametrize("fault", [None, "@P1", {"type": "array"}, [], ["@P999"], ["@P1", "@P1"],
                                  ["@P1", "@P2", "@P999"], ["@P1", "@P2", "@P1"], ["@P1", "@P2", 3]])
def test_annotations_cannot_replace_or_relax_invalid_choices(fault):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate_json(json.dumps({"choices": fault, "title": "Choices", "maxItems": 100}), strict=True)

    with pytest.raises(ValueError):
        asyncio.run(_small_choices(Model(), "", {}, {"@P1", "@P2", "@P3"}, 1, 2, unique=True))


@pytest.mark.parametrize("maximum", [1, 2, 8])
def test_complete_unique_product_lists_can_keep_a_valid_bounded_subset(maximum):
    offered = [f"@P{i}" for i in range(1, 11)]

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            assert schema.model_json_schema()["properties"]["choices"]["maxItems"] == maximum
            return schema.model_validate_json(json.dumps({"choices": offered, "maxItems": maximum}), strict=True)

    assert asyncio.run(_small_choices(Model(), "", {}, set(offered), 1, maximum, unique=True)) == offered[:maximum]
    # Category arrays are positional assignments, so dropping an entry is unsafe.
    with pytest.raises(ValueError):
        asyncio.run(_small_choices(Model(), "", {}, set(offered), maximum, maximum))


@pytest.mark.parametrize("count", [2, 10, 100])
def test_complete_catalog_schema_stays_compact_without_relaxing_rack_keys(count):
    ids = [f"section_{i}" for i in range(count)]
    key = next(iter(CATALOG))

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            context = json.loads(user)
            if issubclass(schema, CategorySelection):
                wire = schema.model_json_schema()
                # The original repeated catalog needed 15K prompt tokens for ten racks.
                assert len(json.dumps(wire)) < 20_000
                Draft202012Validator.check_schema(wire)
                check = Draft202012Validator(wire)
                answer = {"assignments": dict.fromkeys(ids, key)}
                assert check.is_valid(answer)
                assert not check.is_valid({"assignments": {**answer["assignments"], "invented": key}})
                assert not check.is_valid({"assignments": {**answer["assignments"], ids[0]: "invented"}})
                assert not check.is_valid({"assignments": {rid: key for rid in ids[1:]}})
                return schema.model_validate(answer)
            return schema.model_validate({"selections": {key: [context["categories"][key][0]["sku"]]}})

    rows = [StarterRack(id=rid, name="Shelf", type="shelf", available_slots=4) for rid in ids]
    selected = asyncio.run(select_starter_products(Model(), empty_store(), rows, ""))
    assert {row.rack_id for row in selected} == set(ids)
