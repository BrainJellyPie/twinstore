"""Sparse local-model design updates bind each option to its own value type, before caching or applying it."""

import asyncio
import json

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.online import DesignMessage
from store_emulator.engine import llm_client
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.design_chat import DesignChanges, apply_design, chat_design


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("fault", ["none", "duplicate", "unknown", "null", "wrong_type", "extra_field", "mixed", "out_of_range"])
def test_sparse_updates_keep_false_zero_empty_string_and_reject_invalid_patches(monkeypatch, tmp_path, mode, fault):
    original, calls = llm_client.litellm.acompletion, []
    site = build_site("fashion", site_id="sparse")
    site.options.welcome_popup = "coupon"
    site.options.urgency = True
    site.options.coupon_code = "KEEP15"
    before = site.model_dump()
    updates = [{"option": "welcome_popup", "value": "none"}, {"option": "shipping_fee", "value": 0},
               {"option": "urgency", "value": False}, {"option": "coupon_code", "value": ""}]

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        valid = {"updates": updates, "reply": "Removed the popup, delivery fee, urgency and coupon code."}
        invalid = json.loads(json.dumps(valid))
        if fault == "duplicate": invalid["updates"].append({"option": "shipping_fee", "value": 99})
        elif fault == "unknown": invalid["updates"][0]["option"] = "delete_store"
        elif fault == "null": invalid["updates"][0]["value"] = None
        elif fault == "wrong_type": invalid["updates"][1]["value"] = True
        elif fault == "extra_field": invalid["updates"][0]["reason"] = "Not part of the contract"
        elif fault == "mixed": invalid["page_style"] = "neon"
        elif fault == "out_of_range": invalid["updates"].append({"option": "grid_columns", "value": 99})
        if mode == "json_schema":
            schema = body["response_format"]["json_schema"]["schema"]
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
            assert validator.is_valid(valid)
            assert set(schema["properties"]) == {"updates", "reply"}
            if fault not in {"none", "duplicate"}:
                assert not validator.is_valid(invalid)
        answer = invalid if len(calls) == 1 else valid
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/design-sparse", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            messages = [DesignMessage(role="owner", text="Remove the popup, shipping fee, urgency and coupon code. Change nothing else.")]
            reply = await chat_design(client, site, site.options, messages)
            edited, changed = apply_design(site.options, reply.changes, site.currency)
            assert set(changed) == {row["option"] for row in updates}
            assert edited.model_dump() == {**site.options.model_dump(), **{row["option"]: row["value"] for row in updates}}
            assert len(calls) == (1 if fault == "none" else 2)
            used = len(calls)
            cached = await chat_design(client, site, site.options, messages)
            assert cached.model_dump() == reply.model_dump() and len(calls) == used
            assert client.get_usage().cached_requests == 1
            assert site.model_dump() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("currency,amount,expected", [
    ("USD", 4.99, 499), ("USD", 1.005, 101), ("USD", .005, 1),
    ("KRW", .5, 1), ("KRW", 1.5, 2), ("JPY", 2.5, 3), ("JPY", .49, 0),
])
def test_model_money_uses_the_designer_forms_decimal_rounding(currency, amount, expected):
    site = build_site("fashion", site_id="money", currency=currency)
    before = site.options.model_dump()
    edited, _ = apply_design(site.options, DesignChanges(shipping_fee=amount, free_shipping_threshold=amount), currency)
    assert edited.shipping_fee == edited.free_shipping_threshold == expected
    assert site.options.model_dump() == before
