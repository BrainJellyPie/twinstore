"""Oversized catalog requests must reach the existing bounded-task recovery."""

import asyncio
import json
from collections import Counter

import pytest
from instructor.core.exceptions import FailedAttempt, InstructorRetryException
from litellm.exceptions import BadRequestError, ContextWindowExceededError

from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.starter_selection import CategorySelection, ProductSelection, select_starter_products
from tests.engine.test_starter_selection import empty_store
from tests.engine.test_starter_selection_small_tasks import SmallTaskModel


def context_error():
    return ContextWindowExceededError('prompt exceeds the available context', model='openai/local', llm_provider='openai')


def wrapped(error):
    return InstructorRetryException('retries exhausted', n_attempts=2, total_usage=0,
                                    failed_attempts=[FailedAttempt(1, error)])


@pytest.mark.parametrize('stage', ['category', 'product', 'both'])
@pytest.mark.parametrize('wrap', [False, True])
def test_context_overflow_decomposes_without_repeating_the_whole_request(stage, wrap):
    class Limited(SmallTaskModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            fail = (issubclass(schema, CategorySelection) and stage != 'product') or (schema is ProductSelection and stage != 'category')
            if fail:
                self.calls.append((schema, json.loads(user), system))
                error = context_error()
                raise wrapped(error) if wrap else error
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = Limited(category_fault=False, product_fault=False)
    racks = [StarterRack(id=f'section_{i}', name='생활용품 진열대 ' * 20, type='shelf', available_slots=4) for i in range(100)]
    chosen = asyncio.run(select_starter_products(model, empty_store(), racks, '동네 주민',
        allowed_categories={'home_coffee_tea', 'dairy'}, product_limits={'home_coffee_tea': 1}))
    assert Counter(row.rack_id for row in chosen) == Counter(r.id for r in racks)
    assert all(row.category == 'home_coffee_tea' and len(row.skus) == 1 for row in chosen)
    assert sum(issubclass(schema, CategorySelection) for schema, _, _ in model.calls) == 1
    assert sum(schema is ProductSelection for schema, _, _ in model.calls) == 1
    assert len(model.calls) == 2 + (13 if stage != 'product' else 0) + (1 if stage != 'category' else 0)


@pytest.mark.parametrize('wrap', [False, True])
def test_non_context_bad_requests_do_not_start_catalog_recovery(wrap):
    class Rejected:
        calls = 0
        async def generate_structured_async(self, *args, **kwargs):
            self.calls += 1
            error = BadRequestError('unsupported server configuration', model='openai/local', llm_provider='openai')
            raise wrapped(error) if wrap else error
    model = Rejected()
    with pytest.raises(InstructorRetryException if wrap else BadRequestError):
        asyncio.run(select_starter_products(model, empty_store(), [StarterRack(id='a', name='Shelf', type='shelf', available_slots=2)], ''))
    assert model.calls == 1


def test_context_overflow_in_a_small_task_stops_without_partial_assignments():
    class TinyContext:
        calls = 0
        async def generate_structured_async(self, *args, **kwargs):
            self.calls += 1
            raise context_error()
    model = TinyContext()
    store = empty_store()
    before = store.model_dump()
    with pytest.raises(ValueError, match='context'):
        asyncio.run(select_starter_products(model, store, [StarterRack(id='a', name='Shelf', type='shelf', available_slots=2)], ''))
    assert model.calls == 2 and store.model_dump() == before


def test_real_instructor_wrapper_reaches_recovery_after_context_rejection(monkeypatch):
    from litellm import ModelResponse
    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine import llm_client

    calls = []
    async def completion(**kwargs):
        name = kwargs['response_format']['json_schema']['name']
        calls.append(name)
        if name == 'CategorySelection': raise context_error()
        payload = json.loads(kwargs['messages'][-1]['content'])
        if name == 'BoundedCatalogChoices': answer = {'choices': ['home_coffee_tea']}
        else: answer = {'groups': [{'category': key, 'skus': [products[0]['sku']]} for key, products in payload['categories'].items()]}
        return ModelResponse(model='openai/local', choices=[{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(answer)}}])

    monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
    client = llm_client.LiteLLMClient(LLMConfig(model='openai/local-context-test', api_base='http://127.0.0.1:9/v1', structured_output='json_schema'))
    chosen = asyncio.run(select_starter_products(client, empty_store(), [StarterRack(id='a', name='Shelf', type='shelf', available_slots=2)], ''))
    assert len(chosen) == 1 and chosen[0].rack_id == 'a'
    assert calls == ['CategorySelection', 'CategorySelection', 'BoundedCatalogChoices', 'ProductSelection']


@pytest.mark.parametrize('message,recover', [
    ('request (11897 tokens) exceeds the available context size (8192 tokens), try increasing it', True),
    ('input (15119 tokens) is larger than the max context size (8192 tokens). skipping', True),
    ('The context size parameter is not supported by this endpoint', False),
])
def test_llamacpp_http_errors_survive_openai_litellm_and_instructor_translation(monkeypatch, message, recover):
    import httpx
    from openai import AsyncOpenAI
    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine import llm_client

    seen = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            payload = json.loads(request.content)
            name = payload['response_format']['json_schema']['name']
            seen.append(name)
            if name == 'CategorySelection':
                return httpx.Response(400, request=request, json={'error': {'code': 400, 'message': message,
                    'type': 'exceed_context_size_error' if recover else 'invalid_request_error'}})
            user = json.loads(payload['messages'][-1]['content'])
            answer = {'choices': ['home_coffee_tea']} if name == 'BoundedCatalogChoices' else {
                'groups': [{'category': key, 'skus': [products[0]['sku']]} for key, products in user['categories'].items()]}
            return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
                'model': 'local-model', 'choices': [{'index': 0, 'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': json.dumps(answer)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key='offline-test', base_url='http://local.invalid/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, 'client': transport, 'api_key': 'offline-test', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/local-http-context', api_base='http://local.invalid/v1',
                                                       structured_output='json_schema'))
            return await select_starter_products(client, empty_store(), [StarterRack(id='a', name='Shelf', type='shelf', available_slots=2)], '')

    if recover:
        chosen = asyncio.run(exercise())
        assert len(chosen) == 1 and chosen[0].rack_id == 'a'
        assert seen == ['CategorySelection', 'CategorySelection', 'BoundedCatalogChoices', 'ProductSelection']
    else:
        with pytest.raises(InstructorRetryException): asyncio.run(exercise())
        assert seen == ['CategorySelection', 'CategorySelection']
