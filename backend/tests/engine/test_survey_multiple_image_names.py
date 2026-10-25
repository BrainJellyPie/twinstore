"""A description naming different packs must not choose the longest one."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import SurveyRequest
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.survey_design import design_survey


CASES = [
    ("Gold or Silver Pack", [("Gold", "gold"), ("Silver Pack", "silver")], None),
    ("Gold Extra next to Gold", [("Gold", "gold"), ("Gold Extra", "extra")], None),
    ("Green Tea Classic", [("Green Tea", "green"), ("Tea Classic", "classic")], None),
    ("금색 또는 프리미엄 은색", [("금색", "gold"), ("프리미엄 은색", "silver")], None),
    ('"Gold Extra", brand Co', [("Gold", "gold"), ("Gold Extra", "extra")], "extra"),
    ("Gold Extra and Gold Extra", [("Gold", "gold"), ("Gold Extra", "extra")], "extra"),
    ("Gold or Silver Pack", [("Gold", "same"), ("Silver Pack", "same")], "same"),
    ("Green Tea Classic", [("Green Tea", "green"), ("Tea Classic", "classic"), ("Green Tea Classic", "full")], "full"),
]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("asked,images,expected", CASES)
def test_http_and_cached_drafts_do_not_guess_between_multiple_named_images(monkeypatch, tmp_path, mode, reverse, asked, images, expected):
    packages = [(name, aid, "", "") for name, aid in images] + [("Anchor", "anchor", "", ""), ("Other", "other", "", "")]
    if reverse:
        packages.reverse()
    before = list(packages)
    payload = {"name": "Packs", "images": [asked, "Anchor", "Other"], "questions": ["value", "preference"], "reference_price": 2.99}
    calls = []
    async def asend(self, request, *args, **kwargs):
        calls.append(json.loads(request.content))
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "survey-image-names", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}}]})
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model="openai/survey-image-names", api_base="http://127.0.0.1:8081/v1",
        api_key="offline", structured_output=mode, cache_dir=str(tmp_path)))
    async def exercise():
        for repeat in range(2):
            design = await design_survey(client, "Compare the first pack with Anchor and Other", "USD", packages)
            request = SurveyRequest.model_validate(design.model_dump())
            assert request.stimuli == ([expected] if expected else []) + ["anchor", "other"]
            assert request.reference_price == (299 if expected else None)
            assert request.questions == ["value", "preference"]
            if expected:
                assert not design.warnings
                if expected == "same":
                    assert request.stimulus_names[0] == "Silver Pack"
            else:
                assert any("ambiguous" in warning for warning in design.warnings)
                assert any("reference price" in warning for warning in design.warnings)
            assert len(calls) == 1 and client.get_usage().cached_requests == repeat
            assert packages == before
    asyncio.run(exercise())
