"""A different wire format must not reuse a previous mode's model decisions."""
import asyncio
import hashlib
import json

import httpx
import pytest
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    text: str


def responses(monkeypatch):
    seen = []

    def respond(request):
        body = json.loads(request.content)
        mode = 'json_schema' if body['response_format']['type'] == 'json_schema' else 'json'
        seen.append(mode)
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion',
            'created': 0, 'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps({'text': mode})}}]})

    def send(self, request, *args, **kwargs):
        return respond(request)

    async def asend(self, request, *args, **kwargs):
        return respond(request)

    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setattr(httpx.AsyncClient, 'send', asend)
    return seen


def config(path, mode):
    return LLMConfig(model='openai/cache-mode', api_base='http://127.0.0.1:8081/v1',
        structured_output=mode, cache_dir=str(path), temperature=0, seed=None, max_tokens=160, structured_sdk_retries=0)


@pytest.mark.parametrize('order', [('json', 'json_schema'), ('json_schema', 'json')])
@pytest.mark.parametrize('method', ['sync_text', 'async_text', 'sync_image', 'async_image'])
def test_each_mode_reaches_the_sdk_then_reuses_only_its_own_answer(tmp_path, monkeypatch, order, method):
    seen = responses(monkeypatch)
    clients = {mode: LiteLLMClient(config(tmp_path, mode)) for mode in order}
    args = (Answer, 'Give an answer', 'What do you choose?')
    if method.endswith('image'):
        args += ('data:image/png;base64,AA==',)

    async def exercise():
        for mode in [*order, *order]:
            client = clients[mode]
            if method == 'sync_text':
                result = client.generate_structured(*args)
            elif method == 'sync_image':
                result = client.generate_structured_with_image(*args)
            elif method == 'async_text':
                result = await client.generate_structured_async(*args)
            else:
                result = await client.generate_structured_with_image_async(*args)
            assert result.text == mode

    asyncio.run(exercise())
    assert seen == list(order)
    assert all(client.get_usage().cached_requests == 1 for client in clients.values())
    assert len(list(tmp_path.glob('*/*.json'))) == 2


def test_reconfiguring_an_existing_client_changes_the_cache_mode(tmp_path, monkeypatch):
    seen = responses(monkeypatch)
    client = LiteLLMClient(config(tmp_path, 'json'))
    args = (Answer, 'Give an answer', 'What do you choose?')
    assert client.generate_structured(*args).text == 'json'
    client._use(config(tmp_path, 'json_schema'))
    assert client.generate_structured(*args).text == 'json_schema'
    client._use(config(tmp_path, 'json'))
    assert client.generate_structured(*args).text == 'json'
    assert seen == ['json', 'json_schema'] and client.get_usage().cached_requests == 1


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
def test_legacy_cache_without_a_recorded_mode_is_not_assumed_safe(tmp_path, monkeypatch, mode):
    seen = responses(monkeypatch)
    client = LiteLLMClient(config(tmp_path, mode))
    system, user = 'Give an answer', 'What do you choose?'
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
    legacy = {'structured_parser': 'final-think-v2', 'model': client.model, 'api_base': client.api_base,
        'temperature': client.temperature, 'max_tokens': client.max_tokens, 'seed': None,
        'schema': Answer.model_json_schema(), 'messages': messages}
    digest = hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = tmp_path/digest[:2]/f'{digest}.json'
    path.parent.mkdir()
    original = json.dumps({'result': {'text': 'unknown previous format'}})
    path.write_text(original)
    assert client.generate_structured(Answer, system, user).text == mode
    assert seen == [mode] and client.get_usage().cached_requests == 0
    assert path.read_text() == original
