"""Assistive work must reach its local fallback after all configured cloud keys fail."""

import asyncio
from types import SimpleNamespace

import litellm
import pytest
from pydantic import BaseModel

from store_emulator.application import local_vlm, providers
from store_emulator.application.local_vlm import LocalVLMStatus
from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    source: str


@pytest.mark.parametrize('initial', ['anthropic', 'openrouter'])
@pytest.mark.parametrize('mode', ['sync', 'async', 'image', 'text'])
@pytest.mark.parametrize('local_ready', [False, True])
def test_every_rejected_cloud_key_can_be_skipped_before_local_fallback(
    tmp_path, monkeypatch, initial, mode, local_ready,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('PARASTORE_SETTINGS_DIR', str(tmp_path / 'settings'))
    monkeypatch.delenv('TWINSTORE_LOCAL_VLM_AUTO', raising=False)
    monkeypatch.setattr(providers, '_REJECTED_KEYS', {})
    models = []
    for kind in providers._FALLBACK_ORDER:
        preset = providers.PRESETS[kind]
        monkeypatch.setenv(preset.api_key_env, f'offline-{kind}')
        if preset.models:
            fast = next((m for m in preset.models if 'fast' in m.note), preset.models[0])
            models.append(f'{preset.litellm_prefix}/{fast.id}')
    expected = (['openrouter/offline-selected-model'] if initial == 'openrouter' else []) + models
    base = 'http://127.0.0.1:9/v1'
    providers.use_local_server(base)
    status = LocalVLMStatus(state='ready' if local_ready else 'off', api_base=base, slots=1)
    monkeypatch.setattr(local_vlm, 'manager', lambda: SimpleNamespace(status=lambda: status))
    monkeypatch.setattr(local_vlm, 'server_answers', lambda endpoint: local_ready)
    calls = []

    def answer(model):
        calls.append(model)
        if model != 'openai/local-model':
            raise litellm.AuthenticationError('offline rejected key', llm_provider=model.partition('/')[0], model=model)
        return Answer(source=model)

    def create(client, *args):
        return answer(client.model), SimpleNamespace(usage=None)

    async def acreate(client, *args):
        return create(client, *args)

    async def completion(**kwargs):
        result = answer(kwargs['model'])
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content=result.source))])

    monkeypatch.setattr(LiteLLMClient, '_create', create)
    monkeypatch.setattr(LiteLLMClient, '_acreate', acreate)
    monkeypatch.setattr(litellm, 'acompletion', completion)
    client = providers.assistive_client('', LLMConfig(model=expected[0]))

    def run():
        if mode == 'sync':
            return client.generate_structured(Answer, 'system', 'request').source
        if mode == 'text':
            return asyncio.run(client.generate_text_async('system', 'request'))
        if mode == 'image':
            result = asyncio.run(client.generate_structured_with_image_async(Answer, 'system', 'request', 'offline-image'))
        else:
            result = asyncio.run(client.generate_structured_async(Answer, 'system', 'request'))
        return result.source

    if local_ready:
        assert run() == 'openai/local-model'
        assert calls == [*expected, 'openai/local-model']
        assert providers.answered_by(client, '') == 'llamacpp:local'
    else:
        with pytest.raises(ValueError, match='API key'):
            run()
        assert calls == expected


def test_an_erroneous_cyclic_reroute_callback_still_has_a_finite_default_budget(monkeypatch):
    calls = []

    async def refused(client, *args):
        calls.append(client.model)
        raise litellm.AuthenticationError('offline rejected key', llm_provider='openai', model=client.model)

    monkeypatch.setattr(LiteLLMClient, '_acreate', refused)
    client = LiteLLMClient(LLMConfig(model='openai/a'), reroute=lambda tried, error:
                          LLMConfig(model='openai/b' if tried == 'openai/a' else 'openai/a'))
    with pytest.raises(litellm.AuthenticationError):
        asyncio.run(client.generate_structured_async(Answer, 'system', 'request'))
    assert calls == ['openai/a', 'openai/b', 'openai/a', 'openai/b']
