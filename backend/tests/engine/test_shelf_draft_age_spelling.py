"""Known age label spelling must preserve the requested shelf-test panel."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.application.marketing import _quota
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ShelfTestRequest
from store_emulator.domain.persona import AGE_GROUPS, GENDERS
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.shelf_test_design import _Draft, design_shelf_test
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("age", AGE_GROUPS)
def test_http_known_age_spelling_selects_only_requested_people(monkeypatch, tmp_path, mode, age):
    store = target_store()
    before = store.model_dump_json()
    people = [_persona().model_copy(update={"id": f"{group}-{gender}", "age_group": group, "gender": gender})
              for group in AGE_GROUPS for gender in GENDERS]
    snapshots = [person.model_dump() for person in people]
    payload = {"name": "Tea shelf", "product": "Cola 500ml", "shelf": "r1", "promo": "SALE",
               "age_groups": [f"\u3000{age.upper()}\t"]}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shelf-draft-age", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                result = await design_shelf_test(client, f"Test SALE on Cola with shoppers in their {age}", store, "USD", [])
                assert result.age_groups == [age] and result.rack_id == "r1" and result.target_sku == "s-cola"
                assert result.changes[0].promo == "SALE" and not result.warnings
                request = ShelfTestRequest.model_validate({**result.model_dump(), "setup_id": "setup_7d6d"})
                selected = _quota(people, request)
                assert {person.id for person in selected} == {f"{age}-{gender}" for gender in GENDERS}
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat
                assert store.model_dump_json() == before and [person.model_dump() for person in people] == snapshots

    asyncio.run(exercise())


@pytest.mark.parametrize("value", [[None], [True], [20], ["70s"], ["twenties"], ["20"], [{}], {}, "30s"])
def test_unknown_ages_and_wrong_types_do_not_broaden_the_panel(value):
    with pytest.raises(ValidationError):
        _Draft.model_validate_json(json.dumps({"name": "Test", "product": "Tea", "age_groups": value}), strict=True)


@pytest.mark.parametrize("value", [None, []])
def test_unspecified_age_groups_stay_unrestricted(value):
    draft = _Draft.model_validate_json(json.dumps({"name": "Test", "product": "Tea", "age_groups": value}), strict=True)
    assert draft.age_groups == []
