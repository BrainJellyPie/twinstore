"""Per-respondent cache identity must survive disabling provider seeding."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey import likert_summary, survey_panel
from tests.engine.test_survey_model_price_bounds import PERSON


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('concurrency', [1, 6])
@pytest.mark.parametrize('size', [2, 4])
def test_same_profile_respondents_receive_separate_cached_draws_without_provider_seed(
    monkeypatch, tmp_path, mode, concurrency, size,
):
    original, calls = llm_client.litellm.acompletion, []
    people = [PERSON.model_copy(update={'id': f'p{i}'}) for i in range(size)]

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        assert 'seed' not in body
        rating = (len(calls) - 1) % size + 1
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps({'appeal_A': rating})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/unseeded-survey',
                api_base='http://127.0.0.1:8081/v1', structured_output=mode, temperature=0.6, cache_dir=str(tmp_path)))
            with Image.new('RGB', (2, 2)) as board:
                args = (client, people, board, ['appeal'], 1)
                first = await survey_panel(*args, max_concurrent=concurrency, seed=7)
                assert all(not row.error for row in first)
                assert sorted(row.appeal[0] for row in first) == list(range(1, size + 1))
                assert len(calls) == size and len(list(tmp_path.rglob('*.json'))) == size
                summary = likert_summary([row.appeal[0] for row in first], 'appeal', 0)
                assert summary.mean == (size + 1) / 2
                again = await survey_panel(*args, max_concurrent=concurrency, seed=7)
                assert again == first and len(calls) == size
                assert client.get_usage().cached_requests == size
                await survey_panel(*args, max_concurrent=concurrency, seed=8)
                assert len(calls) == 2 * size
                assert len(list(tmp_path.rglob('*.json'))) == 2 * size

    asyncio.run(exercise())


class Answer(BaseModel):
    draw: int


@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('configured_seed', [None, 0, 123])
def test_logical_request_seed_separates_cache_for_both_clients(monkeypatch, tmp_path, asynchronous, configured_seed):
    client = llm_client.LiteLLMClient(LLMConfig(model='openai/local', api_base='http://127.0.0.1:9/v1',
        seed=configured_seed, cache_dir=str(tmp_path)))
    calls = []

    def create(*args):
        calls.append(args)
        return Answer(draw=len(calls)), SimpleNamespace(usage=None)

    async def acreate(*args):
        return create(*args)

    monkeypatch.setattr(client, '_create', create)
    monkeypatch.setattr(client, '_acreate', acreate)
    for seed, expected in [(None, 1), (11, 2), (12, 3), (11, 2), (None, 1), (12, 3)]:
        answer = (asyncio.run(client.generate_structured_async(Answer, 'system', 'request', seed=seed)) if asynchronous
                  else client.generate_structured(Answer, 'system', 'request', seed=seed))
        assert answer.draw == expected
        kwargs = client._call_kwargs(seed)
        assert ('seed' in kwargs) is (configured_seed is not None)
    assert len(calls) == 3 and client.get_usage().cached_requests == 3


def test_disabled_seed_cannot_alias_a_seeded_request_with_the_same_number(tmp_path):
    unseeded = llm_client.LiteLLMClient(LLMConfig(model='openai/local', cache_dir=str(tmp_path)))
    seeded = llm_client.LiteLLMClient(LLMConfig(model='openai/local', seed=0, cache_dir=str(tmp_path)))
    messages = [{'role': 'user', 'content': 'request'}]
    assert unseeded._cache_path(Answer, messages, 11) != seeded._cache_path(Answer, messages, 11)
    assert unseeded._cache_path(Answer, messages, None) != unseeded._cache_path(Answer, messages, 11)
