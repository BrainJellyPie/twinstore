"""Only badge numbers in the current shelf image may be cached as a response."""

import asyncio
import json
from collections import Counter
from dataclasses import replace

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Face
from store_emulator.engine import llm_client
from store_emulator.engine.marketing import shelf_test
from tests.engine.test_shelf_panel_boundaries import person, shelf


@pytest.mark.parametrize("marks", [(1, 2), (2, 7), ()])
@pytest.mark.parametrize("bad_field", ["pick", "noticed_unknown", "noticed_zero", "noticed_negative", "pick_huge"])
@pytest.mark.parametrize("recovers", [False, True])
def test_badge_correction_happens_before_cache_and_pair_comparison(
    tmp_path, monkeypatch, shelf, marks, bad_field, recovers,
):
    rack, view = shelf
    view = replace(view, items=tuple(replace(item, mark=mark) for item, mark in zip(view.items, marks)))
    monkeypatch.setattr(shelf_test, "render_arm", lambda *args: view)
    good = {"pick": marks[0] if marks else 0, "noticed": list(marks), "why": "My choice"}
    bad = {**good}
    if bad_field.startswith("pick"):
        bad["pick"] = 10**100 if bad_field == "pick_huge" else max(marks, default=0) + 1
    else:
        bad["noticed"] = [{"noticed_unknown": max(marks, default=0) + 1,
                            "noticed_zero": 0, "noticed_negative": -1}[bad_field]]
    requests, attempts = [], Counter()
    retry_later = False
    original = llm_client.litellm.acompletion

    async def exercise():
        nonlocal retry_later

        def respond(request):
            sent = json.loads(request.content)
            requests.append(sent)
            key = sent["seed"]
            attempts[key] += 1
            answer = good if retry_later or recovers and attempts[key] > 1 else bad
            return httpx.Response(200, request=request, json={
                "id": "offline-badges", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": json.dumps(answer)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-badge-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))
            args = (client, [person()], rack, rack, Face.N)
            answers = await shelf_test.shelf_panel(*args)
            if not recovers:
                assert all(answer.error for answer in answers)
                assert shelf_test.compare_shelves(answers, "A") == []
                assert not list(tmp_path.rglob("*.json"))
                assert len(requests) == 4
                retry_later = True
                answers = await shelf_test.shelf_panel(*args)
            assert all(not answer.error for answer in answers)
            assert all(answer.pick_sku == ("A" if marks else "") for answer in answers)
            assert all(answer.noticed == (["A", "B"] if marks else []) for answer in answers)
            assert len(shelf_test.compare_shelves(answers, "A", n_bootstrap=20)) == 3
            assert await shelf_test.shelf_panel(*args) == answers
            assert client.get_usage().cached_requests == 2
            assert len(list(tmp_path.rglob("*.json"))) == 2
            for request in requests:
                schema = request["response_format"]["json_schema"]["schema"]["properties"]
                assert schema["pick"]["enum"] == [0, *marks]
                if marks:
                    assert schema["noticed"]["items"]["enum"] == list(marks)
                else:
                    assert schema["noticed"]["maxItems"] == 0

    asyncio.run(exercise())
    assert sorted(attempts.values()) == ([2, 2] if recovers else [3, 3])
