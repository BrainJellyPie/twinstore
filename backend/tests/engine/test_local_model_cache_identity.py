"""A managed server's stable alias must not share responses across model files."""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from store_emulator.application import local_vlm, providers
from store_emulator.application.capture import capture_llm_config
from store_emulator.application.hardware import HardwareProfile, MODEL_BY_KEY, recommend
from store_emulator.application.local_vlm import LocalVLMStatus
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    model_file: str


@pytest.mark.parametrize('mode', ['reference', 'plain', 'capture', 'survey'])
def test_a_new_client_after_model_change_uses_the_new_models_answers(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(providers, 'load_settings', lambda: {})
    plan = recommend(HardwareProfile(os='linux', arch='x64', cores=4, ram_gb=8, ram_free_gb=4))
    status = LocalVLMStatus(state='ready', managed=True, api_base='http://127.0.0.1:8081/v1', slots=1,
                            plan=plan.model_copy(update={'model': MODEL_BY_KEY['qwen3.5-0.8b']}))
    monkeypatch.setattr(local_vlm, 'manager', lambda: SimpleNamespace(status=lambda: status))
    calls = []

    async def create(self, schema, messages, max_retries, seed, max_tokens):
        filename = status.plan.model.file
        calls.append(filename)
        return schema(model_file=filename), SimpleNamespace(usage=None)

    monkeypatch.setattr(LiteLLMClient, '_acreate', create)

    def config():
        if mode in {'capture', 'survey'}:
            out = capture_llm_config(SimulationConfig(), 'llamacpp:local')
            assert out is not None
            return out.model_copy(update={'cache_dir':str(tmp_path / 'survey')}) if mode == 'survey' else out
        base = LLMConfig(cache_dir=str(tmp_path / 'cache'),
                         api_base='http://127.0.0.1:8081/v1' if mode == 'plain' else None)
        return providers.resolve_model('openai/local-vlm' if mode == 'plain' else 'llamacpp:local', base=base, settings={})

    first_config = config()
    first = asyncio.run(LiteLLMClient(first_config).generate_structured_async(Answer, 'Read this shelf', 'same input'))
    status.plan = plan.model_copy(update={'model': MODEL_BY_KEY['qwen3.5-2b']})
    second_config = config()
    second = asyncio.run(LiteLLMClient(second_config).generate_structured_async(Answer, 'Read this shelf', 'same input'))
    repeated = asyncio.run(LiteLLMClient(config()).generate_structured_async(Answer, 'Read this shelf', 'same input'))
    assert first.model_file != second.model_file == status.plan.model.file
    assert repeated == second and calls == [first.model_file, second.model_file]
    assert first_config.model == second_config.model and first_config.api_base == second_config.api_base
    assert 'cache_namespace' not in second_config.model_dump()
    assert 'cache_namespace' not in LiteLLMClient(second_config)._call_kwargs(None)


def test_projector_change_invalidates_image_results_but_not_thread_count_changes(tmp_path, monkeypatch):
    plan = recommend(HardwareProfile(os='linux', arch='x64', cores=4, ram_gb=8, ram_free_gb=4))
    status = LocalVLMStatus(state='ready', managed=True, api_base='http://127.0.0.1:8081/v1', slots=1, plan=plan)
    monkeypatch.setattr(local_vlm, 'manager', lambda: SimpleNamespace(status=lambda: status))
    base = LLMConfig(cache_dir=str(tmp_path))

    def key():
        config = providers.resolve_model('llamacpp:local', base=base, settings={})
        return LiteLLMClient(config)._cache_path(Answer, [{'role':'user','content':'photo'}], 0)

    original = key()
    status.plan = plan.model_copy(update={'threads':plan.threads + 1})
    assert key() == original
    status.plan = plan.model_copy(update={'model':plan.model.model_copy(update={'mmproj':'different-projector.gguf'})})
    assert key() != original


@pytest.mark.parametrize('state,managed', [('off', True), ('ready', False)])
def test_an_unloaded_or_external_servers_recommendation_is_not_its_cache_identity(tmp_path, monkeypatch, state, managed):
    plan = recommend(HardwareProfile(os='linux', arch='x64', cores=4, ram_gb=8, ram_free_gb=4))
    status = LocalVLMStatus(state=state, managed=managed, api_base='http://127.0.0.1:8081/v1', slots=1, plan=plan)
    monkeypatch.setattr(local_vlm, 'manager', lambda: SimpleNamespace(status=lambda: status))
    base = LLMConfig(model='openai/local-model', api_base=status.api_base, cache_dir=str(tmp_path))
    resolved = providers.resolve_model('llamacpp:local', base=base, settings={})
    assert LiteLLMClient(resolved)._cache_path(Answer, [], None) == LiteLLMClient(base)._cache_path(Answer, [], None)


def test_reusing_a_config_for_another_endpoint_clears_the_managed_identity(tmp_path, monkeypatch):
    plan = recommend(HardwareProfile(os='linux', arch='x64', cores=4, ram_gb=8, ram_free_gb=4))
    status = LocalVLMStatus(state='ready', managed=True, api_base='http://127.0.0.1:8081/v1', slots=1, plan=plan)
    monkeypatch.setattr(local_vlm, 'manager', lambda: SimpleNamespace(status=lambda: status))
    managed = providers.resolve_model('llamacpp:local', base=LLMConfig(cache_dir=str(tmp_path)), settings={})
    assert managed.cache_namespace
    external = managed.model_copy(update={'api_base': 'http://127.0.0.1:9090/v1'})
    resolved = providers.resolve_model('openai/local-model', base=external, settings={})
    assert resolved.api_base == external.api_base
    assert resolved.cache_namespace == ''
