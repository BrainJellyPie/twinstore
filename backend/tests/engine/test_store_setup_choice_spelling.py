"""Known opening-day and currency choices must not discard an otherwise valid store form."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.generators.store_setup_writer import _Setup, StoreSetup, draft_store_setup


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("days", ["7", "weekday", "weekend"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_http_known_choices_keep_localized_form_fields_hours_and_cache(monkeypatch, tmp_path, mode, days, currency):
    text = {"name": "우리 동네 Tea Shop", "description": "주민이 찾는 차 가게입니다.", "address": "Mixed Case Address",
            "format": "Tea Shop", "rationale": "Keep User Details"}
    answer = {**text, "open_days": f"\u3000{days.upper()}\t", "currency": f"\t{currency.lower()}\u3000",
              "open_hour": 0, "close_hour": 24}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/store-setup-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            args = (client, "이름과 주소를 유지하고 차 가게를 작성해 주세요.", [("tea", "Tea Shop", "cafe", "Tea")], "ko")
            for repeat in range(2):
                result = await draft_store_setup(*args)
                assert (result.open_days, result.currency, result.open_hour, result.close_hour) == (days, currency, 0, 24)
                assert (result.template_id, result.store_type) == ("tea", "cafe") and not result.warnings
                assert all(getattr(result, key) == value for key, value in text.items() if key != "format")
                assert len(calls) == 2 and client.get_usage().cached_requests == 2 * repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["open_days", "currency"])
@pytest.mark.parametrize("value", ["", "\t", "every day", "weekdays", "EUR", "won", 7, True, [], {}])
def test_unlisted_choices_and_wrong_types_are_not_inferred(field, value):
    with pytest.raises(ValidationError):
        _Setup.model_validate_json(json.dumps({field: value}), strict=True)


def test_null_days_and_currency_remain_unspecified_and_public_result_stays_strict():
    result = _Setup.model_validate_json('{"open_days":null,"currency":null}', strict=True)
    assert result.open_days is result.currency is None
    with pytest.raises(ValidationError):
        StoreSetup(currency="krw")
    with pytest.raises(ValidationError):
        StoreSetup(open_days="Weekday")
