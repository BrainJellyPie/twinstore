"""A missing attention measurement is not an explicit zero-attention response."""

import asyncio
import json
from collections import Counter
from dataclasses import replace

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Face, stable_seed
from store_emulator.engine import llm_client
from store_emulator.engine.marketing import shelf_test
from tests.engine.test_shelf_panel_boundaries import person, shelf


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("missing", [("control",), ("test",), ("control", "test")])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_omitted_attention_is_corrected_or_excluded_before_comparison(monkeypatch, tmp_path, shelf, mode, missing, outcome):
    rack, _ = shelf
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    original, calls, requests = llm_client.litellm.acompletion, Counter(), []
    arms = {stable_seed("shelf", 0, "p", arm) % (2**31 - 1): arm for arm in ("control", "test")}

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        arm = arms[body["seed"]]
        calls[arm] += 1
        payload = {"pick": 2, "noticed": [2, 1], "why": arm}
        if phase == "invalid" and arm in missing and not (outcome == "corrected" and calls[arm] > 1):
            del payload["noticed"]
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shelf-noticed", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path), seed=0))

            async def run():
                return await shelf_test.shelf_panel(client, [person()], rack, rack, Face.N, max_concurrent=1)

            if outcome == "legacy_cache":
                await run()
                paths = list(tmp_path.rglob("*.json"))
                assert len(paths) == 2
                for path in paths:
                    saved = json.loads(path.read_text())
                    if saved["result"]["why"] in missing:
                        del saved["result"]["noticed"]
                        path.write_text(json.dumps(saved))
                phase = "invalid"
            if outcome in {"repeated", "legacy_cache"}:
                before = calls.copy()
                failed = await run()
                assert {answer.arm for answer in failed if answer.error} == set(missing)
                assert all(calls[arm] == before[arm] + 2 for arm in missing)
                assert shelf_test.compare_shelves(failed, "B", n_bootstrap=20) == []
                if outcome == "repeated":
                    assert len(list(tmp_path.rglob("*.json"))) == 2 - len(missing)
                phase = "complete"
            answers = await run()
            assert all(not answer.error and answer.pick_sku == "B" and answer.noticed == ["B", "A"] for answer in answers)
            compared = shelf_test.compare_shelves(answers, "B", n_bootstrap=20)
            assert len(compared) == 3 and all(row.control == row.test == 1 and row.diff == 0 for row in compared)
            if outcome == "corrected":
                assert calls == Counter({arm: 2 if arm in missing else 1 for arm in ("control", "test")})
            before = len(requests)
            assert await run() == answers and len(requests) == before
            saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            assert len(saved) == 2 and all(row["noticed"] == [2, 1] for row in saved)
            if mode == "json_schema":
                schema = requests[0]["response_format"]["json_schema"]["schema"]
                assert "noticed" in schema["required"]

    asyncio.run(exercise())


@pytest.mark.parametrize("empty_face", [False, True])
@pytest.mark.parametrize("pick", [0, 1])
def test_explicit_no_attention_and_empty_shelves_keep_existing_behavior(shelf, monkeypatch, empty_face, pick):
    rack, view = shelf
    if empty_face:
        monkeypatch.setattr(shelf_test, "render_arm", lambda *args: replace(view, items=()))

    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            payload = {"pick": pick} if empty_face else {"pick": pick, "noticed": []}
            return schema.model_validate(payload)

    answers = asyncio.run(shelf_test.shelf_panel(Model(), [person()], rack, rack, Face.N))
    assert all(bool(answer.error) == (empty_face and pick != 0) for answer in answers)
    if not empty_face:
        compared = shelf_test.compare_shelves(answers, "A", n_bootstrap=20)
        assert all(row.control == row.test == 0 for row in compared if row.metric != "pick")
    assert shelf_test.ShelfAnswer(pick=0).noticed == []
