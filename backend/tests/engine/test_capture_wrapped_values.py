"""Observed values in a JSON schema-shaped reply must not silently become an empty label."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.capture.recognize import VLMLabeler
from store_emulator.engine.llm_client import LiteLLMClient


OBSERVED = {"name": "ACME COLA", "brand": "", "size": "500ml", "category": "soft drink",
            "price_text": "$1.00 OFF", "price": 1.0, "confidence": 10}


class Reply:
    def __init__(self, value):
        self.value = value

    async def generate_structured_with_image_async(self, response_model, *args, **kwargs):
        return response_model.model_validate_json(json.dumps(self.value), strict=True)


@pytest.mark.parametrize("wrapped", [False, True])
def test_actual_observations_survive_schema_wrapping(wrapped):
    value = {"description": "shelf product", "properties": OBSERVED} if wrapped else OBSERVED
    with Image.new("RGB", (10, 10), "white") as image:
        label = asyncio.run(VLMLabeler(Reply(value), currency="USD").label(image))
    assert label.model_dump() == OBSERVED


def test_flat_observations_take_precedence_over_a_conflicting_schema_wrapper():
    with Image.new("RGB", (10, 10), "white") as image:
        label = asyncio.run(VLMLabeler(Reply({**OBSERVED, "properties": {"name": "Wrong product"}}), currency="USD").label(image))
    assert label.model_dump() == OBSERVED


@pytest.mark.parametrize("properties", [None, [], {}, {"other": "Cola"}, {"name": {"type": "string", "default": "Cola"}},
    {"name": "Cola", "price": True}, {"name": "Cola", "confidence": 11}])
def test_schema_definitions_and_invalid_wrapped_types_are_not_saved_as_empty_success(properties):
    with Image.new("RGB", (10, 10), "white") as image, pytest.raises(ValidationError):
        asyncio.run(VLMLabeler(Reply({"properties": properties}), currency="USD").label(image))


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_cache_keeps_normalized_values_without_the_outer_schema_wrapper(tmp_path, monkeypatch, mode):
    client = LiteLLMClient(LLMConfig(model="openai/local", api_base="http://127.0.0.1:9/v1",
                                    structured_output=mode, cache_dir=str(tmp_path)))
    calls = []

    async def create(schema, messages, max_retries, seed, max_tokens):
        calls.append(messages)
        return schema.model_validate_json(json.dumps({"properties": OBSERVED}), strict=True), SimpleNamespace(usage=None)

    monkeypatch.setattr(client, "_acreate", create)
    with Image.new("RGB", (10, 10), "white") as image:
        labeler = VLMLabeler(client, currency="USD")
        first = asyncio.run(labeler.label(image))
        assert first.model_dump() == OBSERVED
        assert asyncio.run(labeler.label(image)) == first
    assert len(calls) == 1 and client.get_usage().cached_requests == 1
    cached = [json.loads(p.read_text())["result"] for p in tmp_path.rglob("*.json")]
    assert cached == [OBSERVED]
