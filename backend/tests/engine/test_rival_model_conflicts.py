"""Contradictory model aliases must not change a rival's price index by row order."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.shelf_lab.rival import compare_rival, unmatched_names
from store_emulator.engine.shelf_lab.rival_match import match_products
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_conflicting_rival_matches_retry_before_pricing_and_caching(monkeypatch, tmp_path, mode, reverse, outcome):
    store, capture = pair(our_name="Twin Tea 500 ml", rival_name="Different label", our_price=200, rival_price=100)
    store.racks[0].slots[0].items.append(SlotItem(sku="large", name="Twin Tea 1 L", price=50))
    missing, ours = unmatched_names(store, capture)
    assert missing == ["Different label"]
    good = {"pairs": [{"rival": missing[0], "ours": ours[0]}]}
    bad = {"pairs": [{"rival": missing[0], "ours": name} for name in (ours[::-1] if reverse else ours)]}
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        requests.append(json.loads(request.content))
        payload = bad if phase == "invalid" and not (outcome == "corrected" and len(requests) > 1) else good
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-conflicts", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def match():
                return await match_products(client, missing, ours)

            if outcome == "legacy_cache":
                await match()
                paths = list(tmp_path.rglob("*.json"))
                assert len(paths) == 1
                cached = json.loads(paths[0].read_text())
                cached["result"] = bad
                paths[0].write_text(json.dumps(cached))
                phase = "invalid"
            if outcome in {"repeated", "legacy_cache"}:
                before = len(requests)
                with pytest.raises(InstructorRetryException):
                    await match()
                assert len(requests) == before + 2
                phase = "complete"
            aliases = await match()
            assert aliases == {missing[0]: ours[0]}
            if outcome == "corrected":
                assert len(requests) == 2
            report = compare_rival(store, capture, aliases=aliases)
            assert report.matched == 1 and report.price_index == pytest.approx(0.5)
            assert report.suggested_pull_factor == 1.5 and report.prices[0].our_price == 200
            before = len(requests)
            assert await match() == aliases and len(requests) == before
            saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            assert saved == [good]

    asyncio.run(exercise())


@pytest.mark.parametrize("pairs,expected", [
    ([{"rival": "Label", "ours": "Tea"}, {"rival": "Label", "ours": " TEA "}], {"Label": "Tea"}),
    ([{"rival": "Label", "ours": "Tea"}, {"rival": "Label", "ours": "Invented"}], {"Label": "Tea"}),
    ([{"rival": "Label", "ours": "Tea"}, {"rival": "Other", "ours": "Coffee"}], {"Label": "Tea"}),
    ([{"rival": "Label", "ours": ""}], {}),
    ([], {}),
])
def test_equivalent_duplicates_and_existing_unmatched_controls_remain_supported(pairs, expected):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"pairs": pairs})

    assert asyncio.run(match_products(Model(), ["Label"], ["Tea", "Coffee"])) == expected
