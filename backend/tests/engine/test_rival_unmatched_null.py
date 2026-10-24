"""One explicitly unmatched rival must not erase the remaining valid price comparisons."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.application import shelf_lab
from store_emulator.domain.capture import CaptureItem
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.shelf_lab.rival import compare_rival, unmatched_names
from store_emulator.engine.shelf_lab.rival_match import _Pairs, match_products
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("value", [None, "", "omitted"])
@pytest.mark.parametrize("unmatched", [1, 79])
def test_unmatched_rows_preserve_valid_matches_and_price_index(monkeypatch, tmp_path, mode, value, unmatched):
    store, capture = pair(our_name="Twin Tea 500 ml", rival_name="Different label", our_price=200, rival_price=100)
    capture.items.extend(CaptureItem(id=f"extra-{i}", band=0, level=1, order=i + 1,
        name=f"Unavailable chocolate {i}", price=1, labeled=True) for i in range(unmatched))
    missing, ours = unmatched_names(store, capture)
    assert len(missing) == unmatched + 1
    payload = {"pairs": [{"rival": missing[0], "ours": ours[0]}, *[
        {"rival": name, **({} if value == "omitted" else {"ours": value})} for name in missing[1:]] ]}
    requests, original = [], llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-unmatched", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            aliases = await match_products(client, missing, ours)
            assert aliases == {missing[0]: ours[0]} and len(requests) == 1
            report = compare_rival(store, capture, aliases=aliases)
            assert report.matched == 1 and report.rival_products == unmatched + 1
            assert report.price_index == pytest.approx(0.5) and report.suggested_pull_factor == 1.5
            assert len(report.prices) == 1 and report.prices[0].our_price == 200
            paths = list(tmp_path.rglob("*.json"))
            assert len(paths) == 1
            saved = json.loads(paths[0].read_text())
            assert all(row["ours"] == "" for row in saved["result"]["pairs"][1:])
            assert await match_products(client, missing, ours) == aliases and len(requests) == 1
            # Old cached nulls have the same unmatched meaning and require no model call.
            for row in saved["result"]["pairs"][1:]:
                row["ours"] = None
            paths[0].write_text(json.dumps(saved))
            assert await match_products(client, missing, ours) == aliases and len(requests) == 1

    asyncio.run(exercise())


def test_application_keeps_valid_aliases_without_a_matching_failure_note(monkeypatch):
    store, capture = pair(our_name="Twin Tea 500 ml", rival_name="Different label", our_price=200, rival_price=100)
    capture.items.append(CaptureItem(id="extra", band=0, level=1, order=1, name="Unavailable chocolate", labeled=True))

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"pairs": [{"rival": "Different label", "ours": "Twin Tea 500 ml"},
                {"rival": "Unavailable chocolate", "ours": None}]})

    monkeypatch.setattr(shelf_lab, "assistive_client", lambda *args: Model())
    aliases, note = shelf_lab._model_matches(store, capture, shelf_lab.RivalRequest(setup_id="setup_test"), SimulationConfig())
    assert not note and aliases == {"Different label": "Twin Tea 500 ml"}


@pytest.mark.parametrize("payload", [
    {"pairs": None}, {"pairs": [{"rival": None, "ours": "Tea"}]},
    {"pairs": [{"ours": "Tea"}]}, {"pairs": [{"rival": "Label", "ours": 42}]},
])
def test_missing_identity_or_malformed_match_structure_stays_invalid(payload):
    with pytest.raises(ValidationError):
        _Pairs.model_validate(payload)
