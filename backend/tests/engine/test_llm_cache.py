from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient


class _Answer(BaseModel):
    text: str


def test_cache_roundtrip_and_key_sensitivity(tmp_path):
    client = LiteLLMClient(LLMConfig(model="openai/local", cache_dir=str(tmp_path), seed=1))
    msgs = [{"role": "user", "content": "hi"}]
    path = client._cache_path(_Answer, msgs, seed=5)  # pyright: ignore[reportPrivateUsage]
    assert path is not None and not path.exists()
    client._cache_put(path, _Answer(text="hello"))  # pyright: ignore[reportPrivateUsage]
    cached = client._cache_get(path, _Answer)  # pyright: ignore[reportPrivateUsage]
    assert cached == _Answer(text="hello")
    usage = client.get_usage()
    assert usage.requests == 1 and usage.cached_requests == 1
    assert client._cache_path(_Answer, msgs, seed=6) != path  # pyright: ignore[reportPrivateUsage]
    assert client._cache_path(_Answer, [{"role": "user", "content": "bye"}], seed=5) != path  # pyright: ignore[reportPrivateUsage]


def test_seed_is_only_sent_when_enabled():
    off = LiteLLMClient(LLMConfig(model="openai/local"))
    on = LiteLLMClient(LLMConfig(model="openai/local", seed=7, api_base="http://127.0.0.1:8080/v1"))
    assert "seed" not in off._call_kwargs(3)  # pyright: ignore[reportPrivateUsage]
    kwargs = on._call_kwargs(3)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(kwargs["seed"], int) and kwargs["api_base"] == "http://127.0.0.1:8080/v1"
    assert on._call_kwargs(3) == on._call_kwargs(3)  # pyright: ignore[reportPrivateUsage]
    assert on._call_kwargs(3)["seed"] != on._call_kwargs(4)["seed"]  # pyright: ignore[reportPrivateUsage]
