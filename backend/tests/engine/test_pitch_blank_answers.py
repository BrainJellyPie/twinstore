"""Whitespace-only required narratives cannot form a complete script-rating pair."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.staff_pitch import PitchRating
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.staff_pitch import test_pitch_panel as run_panel
from tests.engine.test_staff_pitch import PRODUCT, report, request as pitch_request
from tests.engine.test_survey_model_price_bounds import PERSON


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["reply", "reason"])
@pytest.mark.parametrize("value", ["   ", "\t\n\u3000\u2003"])
@pytest.mark.parametrize("bad_arm", ["a", "b"])
@pytest.mark.parametrize("legacy_cache", [False, True])
def test_blank_rating_narratives_are_excluded_and_only_complete_answers_are_reused(
    monkeypatch, tmp_path, mode, field, value, bad_arm, legacy_cache,
):
    req = pitch_request()
    phase = "complete" if legacy_cache else "invalid"
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        user = json.loads(next(row["content"] for row in body["messages"] if row["role"] == "user"))
        arm = "a" if user["employee_script"] == req.variants[0].script else "b"
        requests.append(arm)
        payload = {"purchase_intent": 1 if arm == "a" else 5, "trust": 3, "pressure": 2,
                   "reply": "No.", "reason": "I already have enough tea."}
        if phase == "invalid" and arm == bad_arm:
            payload[field] = value
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/pitch-blank", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                return await run_panel(client, [PERSON], req, PRODUCT)

            if legacy_cache:
                await run()
                paths = list(tmp_path.rglob("*.json"))
                assert len(paths) == 2
                for path in paths:
                    saved = json.loads(path.read_text())
                    if saved["result"]["purchase_intent"] == (1 if bad_arm == "a" else 5):
                        saved["result"][field] = value
                        path.write_text(json.dumps(saved))
                phase = "invalid"
            before = len(requests)
            failed = await run()
            assert getattr(failed[0], bad_arm) is None and getattr(failed[0], f"error_{bad_arm}")
            other = "b" if bad_arm == "a" else "a"
            assert getattr(failed[0], other) is not None and not getattr(failed[0], f"error_{other}")
            summary = report(failed)
            assert (summary.attempted, summary.pairs, summary.excluded) == (1, 0, 1)
            assert summary.comparisons == [] and summary.segments == [] and summary.screening_leader is None
            assert len(requests) == before + (1 if legacy_cache else 2)  # Existing one-attempt panel budget.
            if not legacy_cache:
                assert len(list(tmp_path.rglob("*.json"))) == 1
            phase = "complete"
            before = len(requests)
            recovered = await run()
            assert recovered[0].a is not None and recovered[0].b is not None
            assert not recovered[0].error_a and not recovered[0].error_b
            assert report(recovered).pairs == 1 and len(requests) == before + 1
            before = len(requests)
            cached = await run()
            assert [row.model_dump() for row in cached] == [row.model_dump() for row in recovered]
            assert len(requests) == before
            for path in tmp_path.rglob("*.json"):
                saved = json.loads(path.read_text())["result"]
                assert saved["reply"] == "No." and saved["reason"] == "I already have enough tea."

    asyncio.run(exercise())


@pytest.mark.parametrize("reply,reason", [("No.", "Enough tea."), ("  No.\t", "\u3000충분해요.\n")])
def test_short_negative_and_unicode_answers_remain_valid(reply, reason):
    rating = PitchRating(purchase_intent=1, trust=3, pressure=2, reply=reply, reason=reason)
    assert rating.reply == reply.strip() and rating.reason == reason.strip()
