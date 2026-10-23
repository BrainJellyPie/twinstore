"""A malformed cache entry must not permanently block a model workflow or its retries."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("entry", [None, False, 7, "cached", [], ["cached"], {},
                                   {"result": None}, {"result": []}, {"result": {"text": 3}}])
def test_invalid_cache_falls_through_to_model_and_is_replaced(tmp_path, monkeypatch, asynchronous, entry):
    client = LiteLLMClient(LLMConfig(model="openai/local", api_base="http://127.0.0.1:9/v1", cache_dir=str(tmp_path)))
    messages, _ = client._messages("system", "customer request")
    path = client._cache_path(Answer, messages, None)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(entry))
    calls = []

    def create(*args):
        calls.append(args)
        return Answer(text="recovered"), SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15))

    async def acreate(*args):
        return create(*args)

    monkeypatch.setattr(client, "_create", create)
    monkeypatch.setattr(client, "_acreate", acreate)
    for _ in range(2):
        if asynchronous:
            answer = asyncio.run(client.generate_structured_async(Answer, "system", "customer request"))
        else:
            answer = client.generate_structured(Answer, "system", "customer request")
        assert answer.text == "recovered"
    assert len(calls) == 1
    assert json.loads(path.read_text())["result"] == {"text": "recovered"}
    usage = client.get_usage()
    assert usage.requests == 2 and usage.cached_requests == 1
    assert usage.prompt_tokens == 10 and usage.completion_tokens == 5
