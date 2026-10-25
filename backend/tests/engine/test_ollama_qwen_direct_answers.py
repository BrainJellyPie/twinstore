"""Known native Qwen3.5 models must retain their short budget for the answer."""

import asyncio
import hashlib
import json

import pytest
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from tests.engine.test_ollama_finish_reason import native_transport


class Reply(BaseModel):
    text: str


@pytest.mark.parametrize("model", ["qwen3.5:2b", "library/qwen3.5:9b", "registry.ollama.ai/library/qwen3.5:4b"])
@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
def test_native_qwen_uses_the_answer_budget_in_every_request_path(native_transport, model, mode, structured):
    calls = []

    def respond(body):
        calls.append(body)
        # The official Qwen3.5 renderer defaults to thinking. A short budget can
        # finish there before the final content; the native cutoff stays explicit.
        return ('{"text":"ready"}', "stop") if body.get("think") is False else ("", "length")

    native_transport(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/" + model, api_base="http://127.0.0.1:11434",
        max_tokens=160, structured_output=structured))
    args = (Reply, "Answer directly.", "Reply ready.")
    if mode == "sync": result = client.generate_structured(*args)
    elif mode == "sync_image": result = client.generate_structured_with_image(*args, "data:image/png;base64,AA==")
    elif mode == "async": result = asyncio.run(client.generate_structured_async(*args))
    elif mode == "async_image": result = asyncio.run(client.generate_structured_with_image_async(*args, "data:image/png;base64,AA=="))
    else: result = Reply.model_validate_json(asyncio.run(client.generate_text_async(*args[1:])))
    assert result.text == "ready" and len(calls) == 1
    assert calls[0]["think"] is False and calls[0]["truncate"] is False and calls[0]["shift"] is False
    assert calls[0]["options"]["num_predict"] == 160 and "think" not in calls[0]["options"]


@pytest.mark.parametrize("model,base", [
    ("ollama_chat/gpt-oss:20b", "http://127.0.0.1:11434"),
    ("ollama_chat/deepseek-r1:8b", "http://127.0.0.1:11434"),
    ("ollama_chat/custom-qwen3.5", "http://127.0.0.1:11434"),
    ("ollama_chat/someone/qwen3.5:2b", "http://127.0.0.1:11434"),
    ("ollama_chat/qwen3.5-custom:2b", "http://127.0.0.1:11434"),
    ("ollama_chat/qwen3.5:cloud", "http://127.0.0.1:11434"),
    ("ollama_chat/qwen3.5:397b-cloud", "http://127.0.0.1:11434"),
    ("ollama_chat/qwen3.5:2b", "https://OLLAMA.COM./api/chat"),
    ("openai/qwen3.5:2b", "http://127.0.0.1:8081/v1"),
    ("ollama_chat/qwen3.5:2b", "http://[invalid"),
])
def test_native_switch_is_not_guessed_for_other_models_cloud_or_invalid_endpoints(model, base):
    kwargs = LiteLLMClient(LLMConfig(model=model, api_base=base))._call_kwargs(None, structured=True)
    assert "think" not in kwargs.get("extra_body", {})


@pytest.mark.parametrize("base", [None, "http://localhost:11434", "http://192.0.2.25:11434", "https://models.example.test"])
def test_official_family_policy_applies_to_native_self_hosted_endpoints(base):
    client = LiteLLMClient(LLMConfig(model="ollama_chat/qwen3.5", api_base=base))
    assert client._call_kwargs(None)["extra_body"]["think"] is False


@pytest.mark.parametrize("model", ["qwen3.5:2b", "gpt-oss:20b"])
def test_only_changed_thinking_policy_separates_old_cached_answers(tmp_path, model):
    client = LiteLLMClient(LLMConfig(model="ollama_chat/" + model, api_base="http://127.0.0.1:11434", cache_dir=str(tmp_path)))
    messages = [{"role": "user", "content": "Hello"}]
    old_key = hashlib.sha256(json.dumps({"ollama_finish_reason": "native-v1", "ollama_context": "preserve-context-v2",
        "structured_parser": "final-think-v2", "model": client.model, "api_base": client.api_base,
        "temperature": client.temperature, "max_tokens": client.max_tokens, "seed": client._effective_seed(None),
        "schema": Reply.model_json_schema(), "messages": messages}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old_path = tmp_path / old_key[:2] / f"{old_key}.json"
    client._cache_put(old_path, Reply(text="previous policy"))
    current_path = client._cache_path(Reply, messages, None)
    if model.startswith("qwen3.5"):
        assert current_path != old_path and client._cache_get(current_path, Reply) is None
        client._cache_put(current_path, Reply(text="current policy"))
        assert client._cache_get(current_path, Reply).text == "current policy"
    else:
        assert current_path == old_path and client._cache_get(current_path, Reply).text == "previous policy"
    assert old_path.exists()
