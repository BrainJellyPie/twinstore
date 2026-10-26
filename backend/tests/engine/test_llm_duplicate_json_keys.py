"""Duplicate JSON keys must trigger a bounded correction, not silently replace data."""
import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client


class Person(BaseModel):
    description: str


class Reply(BaseModel):
    people: list[Person]


GOOD = '{"people":[{"description":"A student buying textbooks"}]}'
BAD = {
    'nested': '{"people":[{"description":"A student buying textbooks","description":"Walks slowly"}]}',
    'root': '{"people":[{"description":"A student buying textbooks"}],"people":[{"description":"Walks slowly"}]}',
    'escaped': r'{"people":[{"description":"A student buying textbooks","descr\u0069ption":"Walks slowly"}]}',
    'identical': '{"people":[{"description":"A student buying textbooks","description":"A student buying textbooks"}]}',
}


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('kind', ['sync', 'async', 'sync_image', 'async_image'])
@pytest.mark.parametrize('fault', list(BAD))
def test_conflicting_object_members_are_corrected_before_return_and_cache(monkeypatch, tmp_path, mode, kind, fault):
    original_sync, original_async = llm_client.litellm.completion, llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) > 1:
            assert 'Duplicate JSON object key' in json.dumps(body['messages'])
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant',
                'content': BAD[fault] if len(calls) == 1 else GOOD}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as ah:
            with httpx.Client(transport=httpx.MockTransport(respond)) as sh:
                sync = OpenAI(api_key='offline', base_url='http://127.0.0.1:9/v1', http_client=sh, max_retries=0)
                asynchronous = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:9/v1', http_client=ah, max_retries=0)

                def completion(**kwargs):
                    return original_sync(**{**kwargs, 'client': sync, 'api_key': 'offline', 'num_retries': 0})

                async def acompletion(**kwargs):
                    return await original_async(**{**kwargs, 'client': asynchronous, 'api_key': 'offline', 'num_retries': 0})

                monkeypatch.setattr(llm_client.litellm, 'completion', completion)
                monkeypatch.setattr(llm_client.litellm, 'acompletion', acompletion)
                client = llm_client.LiteLLMClient(LLMConfig(model='openai/duplicate-keys', api_base='http://127.0.0.1:9/v1',
                    structured_output=mode, cache_dir=str(tmp_path)))

                async def ask():
                    if kind == 'sync': return client.generate_structured(Reply, 'Describe people', 'One student', max_retries=2)
                    if kind == 'sync_image': return client.generate_structured_with_image(Reply, 'Describe people', 'One student', 'data:image/png;base64,AA==', max_retries=2)
                    if kind == 'async_image': return await client.generate_structured_with_image_async(Reply, 'Describe people', 'One student', 'data:image/png;base64,AA==', max_retries=2)
                    return await client.generate_structured_async(Reply, 'Describe people', 'One student', max_retries=2)

                first = await ask()
                assert first.people[0].description == 'A student buying textbooks'
                assert len(calls) == 2
                usage = client.get_usage()
                assert (usage.requests, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (2, 20, 10, 30)
                assert (await ask()).model_dump() == first.model_dump()
                assert len(calls) == 2 and client.get_usage().cached_requests == 1
                entries = list(tmp_path.glob('*/*.json'))
                assert len(entries) == 1 and json.loads(entries[0].read_text())['result'] == json.loads(GOOD)

    asyncio.run(exercise())


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('case', ['repeated', 'corrupt_cache', 'separate_objects', 'quoted_json', 'reasoning', 'fenced'])
def test_duplicate_rejection_is_bounded_without_losing_valid_text_or_cache(monkeypatch, tmp_path, mode, case):
    from instructor.core.exceptions import InstructorRetryException
    from litellm import ModelResponse

    calls = []
    valid = GOOD
    if case == 'separate_objects': valid = '{"people":[{"description":"One"},{"description":"Two"}]}'
    if case == 'quoted_json': valid = json.dumps({'people': [{'description': BAD['nested']}]})
    content = f'<think>{BAD["nested"]}</think>{valid}' if case == 'reasoning' else f'```json\n{valid}\n```' if case == 'fenced' else valid

    async def completion(**kwargs):
        calls.append(kwargs)
        return ModelResponse(model='openai/duplicate-keys', usage={'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            choices=[{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant',
                'content': BAD['nested'] if case == 'repeated' else content}}])

    monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
    client = llm_client.LiteLLMClient(LLMConfig(model='openai/duplicate-keys', api_base='http://127.0.0.1:9/v1',
        structured_output=mode, cache_dir=str(tmp_path)))

    async def exercise():
        async def ask():
            return await client.generate_structured_async(Reply, 'Describe people', 'One student', max_retries=2)
        if case == 'repeated':
            with pytest.raises(InstructorRetryException) as caught:
                await ask()
            assert len(caught.value.failed_attempts) == 2
            assert all(isinstance(row.exception, json.JSONDecodeError) for row in caught.value.failed_attempts)
            assert not list(tmp_path.glob('*/*.json'))
            usage = client.get_usage()
            assert len(calls) == usage.requests == 2 and usage.total_tokens == 30
            return
        result = await ask()
        assert result.model_dump() == json.loads(valid)
        if case == 'corrupt_cache':
            path = next(tmp_path.glob('*/*.json'))
            path.write_text('{"result":' + valid + ',"result":' + BAD['nested'] + '}')
            assert (await ask()).model_dump() == json.loads(valid)
            assert len(calls) == 2 and client.get_usage().cached_requests == 0
        else:
            assert len(calls) == 1

    asyncio.run(exercise())


def test_guard_preserves_real_response_schemas_and_parent_validation():
    from store_emulator.engine.generators.persona import GeneratedPersona, traffic_response_model
    from store_emulator.engine.starter_selection import CategorySelection
    from store_emulator.engine.online.prompt import choice_model
    from pydantic import ValidationError

    for model in [Reply, GeneratedPersona, traffic_response_model(9, 12, identities=['Student']), CategorySelection, choice_model([2, 7], 2)]:
        wrapped = llm_client._unique_response_model(model)
        assert issubclass(wrapped, model)
        assert wrapped.model_json_schema() == model.model_json_schema()
    wrapped = llm_client._unique_response_model(choice_model([2, 7], 2))
    with pytest.raises(ValidationError, match='search box'):
        wrapped.model_validate_json('{"option":2,"search_text":""}')
    assert wrapped.model_validate_json('{"option":7}').model_dump()['option'] == 7
