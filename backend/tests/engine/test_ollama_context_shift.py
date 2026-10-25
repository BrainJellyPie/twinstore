"""Native generation must not silently forget input after filling its context."""

import asyncio
import hashlib
import json
import re

import pytest
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine.generators import persona as gen
from store_emulator.engine.llm_client import LiteLLMClient
from tests.engine.test_customer_truncated_batches import hourly, profile
from tests.engine.test_ollama_finish_reason import native_transport


class Reply(BaseModel):
    text: str


@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
def test_context_shift_control_reaches_the_native_top_level(native_transport, mode, structured):
    calls = []
    def respond(body):
        calls.append(body)
        return '{"text":"ready"}', "stop"
    native_transport(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context-shift", api_base="http://127.0.0.1:11434", structured_output=structured))
    args = (Reply, "Keep customer conditions.", "Write the answer.")
    if mode == "sync": result = client.generate_structured(*args)
    elif mode == "sync_image": result = client.generate_structured_with_image(*args, "data:image/png;base64,AA==")
    elif mode == "async": result = asyncio.run(client.generate_structured_async(*args))
    elif mode == "async_image": result = asyncio.run(client.generate_structured_with_image_async(*args, "data:image/png;base64,AA=="))
    else: result = Reply.model_validate_json(asyncio.run(client.generate_text_async(*args[1:])))
    assert result.text == "ready" and len(calls) == 1
    assert calls[0].get("shift") is False and calls[0].get("truncate") is False
    assert "shift" not in calls[0].get("options", {})


@pytest.mark.parametrize("count", [4, 5, 12])
def test_full_context_cutoff_reaches_customer_recovery_instead_of_accepting_forgotten_rows(native_transport, count):
    calls = []
    def respond(body):
        prompt = next(m["content"] for m in body["messages"] if m["role"] == "user" and "페르소나" in m["content"])
        hours = [int(h) for h in re.findall(r"^\[\d+\] (\d+)시", prompt, re.MULTILINE)]
        calls.append(len(hours))
        if len(hours) == count:
            if body.get("shift") is False:
                return '{"personas":[', "length"
            # Valid short output cannot reveal that earlier requested rows were
            # lost during context shifting. Represent that protocol risk here.
            hours = hours[-1:]
        return json.dumps({"personas": [gen.GeneratedPersona(identity="resident", age_group="30s", gender="Female",
            description=f"Arrived at {h}", intent="Buy groceries", purpose="groceries").model_dump() for h in hours]}), "stop"
    native_transport(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context-shift", api_base="http://127.0.0.1:11434", structured_output="json_schema"))
    people = asyncio.run(gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hourly(count), batch_size=count, seed=42))
    assert [p.arrival_hour for p in people] == list(range(9, 9 + count))
    assert [p.description for p in people] == [f"Arrived at {h}" for h in range(9, 9 + count)]
    assert calls == [count, count, count, count // 2, count - count // 2]
    assert client.get_usage().total_tokens == 75


def test_cache_from_input_only_preservation_does_not_bypass_full_context_policy(tmp_path):
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context-shift", api_base="http://127.0.0.1:11434", cache_dir=str(tmp_path)))
    messages = [{"role": "user", "content": "Hello"}]
    old_key = hashlib.sha256(json.dumps({"ollama_finish_reason": "native-v1", "ollama_context": "preserve-input-v1",
        "structured_parser": "final-think-v2", "model": client.model, "api_base": client.api_base,
        "temperature": client.temperature, "max_tokens": client.max_tokens, "seed": client._effective_seed(None),
        "schema": Reply.model_json_schema(), "messages": messages}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old_path = tmp_path / old_key[:2] / f"{old_key}.json"
    client._cache_put(old_path, Reply(text="earlier conditions forgotten"))
    assert client._cache_get(client._cache_path(Reply, messages, None), Reply) is None
    assert old_path.exists()
