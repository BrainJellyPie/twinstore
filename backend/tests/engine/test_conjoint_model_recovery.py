"""A syntactically valid model draft must be usable before it reaches the response cache."""

import asyncio
import copy
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ConjointRequest
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.conjoint_design import _Draft, design_conjoint, to_design


GOOD = {
    "name": "Tea choices", "product": "Tea", "prices": [1, 2],
    "attributes": [{"name": "Style", "levels": ["Regular", "Zero"]},
                   {"name": "Pack", "levels": ["Can", "Bottle"]}],
}

INVALID = [
    pytest.param("USD", {"product": "   "}, id="blank-product"),
    pytest.param("USD", {"attributes": [{"name": "Price", "levels": ["Low", "High"]}]}, id="price-only"),
    pytest.param("USD", {"attributes": [{"name": " ", "levels": ["Low", "High"]}]}, id="blank-attribute"),
    pytest.param("USD", {"attributes": [{"name": "Style", "levels": ["Regular", " regular "]}]}, id="repeated-level"),
    pytest.param("USD", {"attributes": [{"name": "Style", "levels": [" ", "\t"]}]}, id="blank-levels"),
    pytest.param("USD", {"attributes": [{"name": "Style", "levels": ["x" * 60 + "a", "x" * 60 + "b"]}]},
                 id="levels-collide-after-truncation"),
    pytest.param("USD", {"attributes": [{"name": "Style", "levels": ["Regular", "Zero"]}], "prices": []}, id="single-axis"),
    pytest.param("USD", {"attributes": [{"name": "Style", "levels": ["Regular", "Zero"]},
                                        {"name": " style ", "levels": ["Can", "Bottle"]}], "prices": []},
                 id="duplicate-axes"),
    pytest.param("USD", {"prices": [1]}, id="one-price"),
    pytest.param("USD", {"prices": [1, 1]}, id="repeated-price"),
    pytest.param("USD", {"prices": [1.001, 1.002]}, id="cents-collapse"),
    pytest.param("JPY", {"prices": [1.1, 1.2]}, id="yen-collapse"),
    pytest.param("USD", {"prices": [.001, 1]}, id="sub-cent"),
    pytest.param("KRW", {"prices": [.49, 1]}, id="sub-won"),
    pytest.param("USD", {"prices": [1e308, 1]}, id="huge-finite"),
    pytest.param("USD", {"prices": [float("inf"), 1]}, id="infinite"),
    pytest.param("USD", {"prices": [float("nan"), 1, 2]}, id="nan"),
    pytest.param("USD", {"prices": [90071992547409.92, 1]}, id="unsafe-cents"),
    pytest.param("JPY", {"prices": [9007199254740992.0, 1]}, id="unsafe-yen"),
]


@pytest.mark.parametrize("currency,patch", INVALID)
@pytest.mark.parametrize("recovers", [False, True])
def test_semantic_failure_is_corrected_before_caching_and_a_later_retry_can_recover(
    tmp_path, monkeypatch, currency, patch, recovers,
):
    bad = {**copy.deepcopy(GOOD), **patch}
    # These errors survive the JSON response schema; they fail only when used as a study.
    with pytest.raises(ValueError):
        to_design(_Draft.model_validate(bad), currency, [])
    requests = []
    retry_later = False
    original = llm_client.litellm.acompletion

    async def exercise():
        nonlocal retry_later

        def respond(request):
            requests.append(json.loads(request.content))
            payload = GOOD if retry_later or recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={
                "id": "offline-conjoint", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-conjoint-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))
            if not recovers:
                with pytest.raises(InstructorRetryException):
                    await design_conjoint(client, "Compare tea choices", currency, [])
                assert len(requests) == 2
                assert not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await design_conjoint(client, "Compare tea choices", currency, [])
            assert result == to_design(_Draft.model_validate(GOOD), currency, [])
            ConjointRequest.model_validate(result.model_dump())
            assert await design_conjoint(client, "Compare tea choices", currency, []) == result
            assert client.get_usage().cached_requests == 1
            cached = [json.loads(p.read_text())["result"] for p in tmp_path.rglob("*.json")]
            assert len(cached) == 1 and cached[0]["prices"] == GOOD["prices"]
            assert cached[0]["attributes"] == GOOD["attributes"]

    asyncio.run(exercise())
    assert len(requests) == (2 if recovers else 3)
    assert "validation" in json.dumps(requests[1]["messages"]).lower()


def test_simultaneous_currencies_keep_their_validation_and_cache_identity(tmp_path, monkeypatch):
    counts = {"USD": 0, "JPY": 0}
    original = llm_client.litellm.acompletion

    async def exercise():
        async def respond(request):
            payload = json.loads(request.content)
            currency = "USD" if "price levels in USD" in payload["messages"][0]["content"] else "JPY"
            counts[currency] += 1
            await asyncio.sleep(0)
            prices = [1.01, 1.02] if counts[currency] == 1 else [1, 2]
            return httpx.Response(200, request=request, json={
                "id": "offline-currencies", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": json.dumps({**GOOD, "prices": prices})}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-conjoint-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))
            results = await asyncio.gather(*(design_conjoint(client, "Compare tea choices", currency, [])
                                             for currency in ("USD", "JPY")))
            assert [result.prices for result in results] == [[101, 102], [1, 2]]
            assert await asyncio.gather(*(design_conjoint(client, "Compare tea choices", currency, [])
                                          for currency in ("USD", "JPY"))) == results
            assert client.get_usage().cached_requests == 2
            assert len(list(tmp_path.rglob("*.json"))) == 2

    asyncio.run(exercise())
    assert counts == {"USD": 1, "JPY": 2}
