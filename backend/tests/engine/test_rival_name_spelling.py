"""Copied names may vary in case/space, but ambiguous Unicode identities cannot pick a price."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.shelf_lab.rival import compare_rival, unmatched_names
from store_emulator.engine.shelf_lab.rival_match import match_products
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("case", ["rival_case", "rival_spaces", "both_variants", "unicode_exact",
    "unicode_spaces", "unicode_ambiguous", "rival_ambiguous", "rival_exact_collision", "unknown_name"])
def test_copied_names_resolve_without_order_dependent_price_choices(monkeypatch, tmp_path, mode, reverse, case):
    ours = "Maße Tea 500 ml" if case.startswith("unicode") else "Twin Tea 500 ml"
    store, capture = pair(our_name=ours, rival_name="Different label", our_price=200, rival_price=100)
    if case.startswith("unicode"):
        store.racks[0].slots[0].items.append(SlotItem(sku="other", name="Masse Tea 500 ml", price=50))
    if case in {"rival_ambiguous", "rival_exact_collision"}:
        capture.items.append(capture.items[0].model_copy(update={"id": "other", "name": "different label"}))
    if reverse:
        store.racks[0].slots[0].items.reverse()
        capture.items.reverse()
    missing, names = unmatched_names(store, capture)
    asked, target = "Different label", ours
    if case in {"rival_case", "both_variants", "rival_ambiguous"}:
        asked = "DIFFERENT LABEL"
    if case in {"rival_spaces", "both_variants"}:
        asked = " \t" + asked + "\n"
    if case == "both_variants":
        target = " " + ours.upper() + " "
    if case == "unicode_spaces":
        target = " " + ours + " "
    if case == "unicode_ambiguous":
        target = "MASSE TEA 500 ML"
    if case == "unknown_name":
        target = "Invented Tea 500 ml"
    expected = {} if case in {"unicode_ambiguous", "rival_ambiguous", "unknown_name"} else {"Different label": ours}
    before = store.model_dump(), capture.model_dump()
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"pairs": [{"rival": asked, "ours": target}]})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            aliases = await match_products(client, missing, names)
            assert aliases == expected
            report = compare_rival(store, capture, aliases=aliases)
            assert report.matched == (1 if expected else 0)
            assert report.price_index == (pytest.approx(.5) if expected else None)
            assert report.suggested_pull_factor == (1.5 if expected else None)
            assert await match_products(client, missing, names) == aliases and len(requests) == 1
            assert client.get_usage().cached_requests == 1
            assert (store.model_dump(), capture.model_dump()) == before

    asyncio.run(exercise())


@pytest.mark.parametrize("first,second", [(" Different label ", "Different label"), ("DIFFERENT LABEL", "Different label")])
@pytest.mark.parametrize("reverse", [False, True])
def test_spelling_changes_cannot_hide_a_contradictory_unmatched_answer(first, second, reverse):
    from pydantic import ValidationError

    pairs = [{"rival": first, "ours": "Tea"}, {"rival": second, "ours": ""}]

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"pairs": pairs[::-1] if reverse else pairs})

    with pytest.raises(ValidationError, match="Conflicting matches"):
        asyncio.run(match_products(Model(), ["Different label"], ["Tea"]))
