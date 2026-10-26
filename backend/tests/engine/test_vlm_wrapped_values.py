"""Actual values under properties are usable; schema definitions are not measurements."""
import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.simulation.engines.vlm_glance.prompt import resolve, shelf_glance_model
from tests.engine.test_shelf_panel_boundaries import shelf


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('wrapped', [False, True])
@pytest.mark.parametrize('chosen', [False, True])
def test_values_survive_sdk_validation_resolution_and_cache(monkeypatch, tmp_path, shelf, mode, wrapped, chosen):
    _, view = shelf
    schema = shelf_glance_model(view)
    value = {'product': 'Banana' if chosen else '', 'number': 2 if chosen else 0,
             'interest': 9 if chosen else 0, 'reason': 'Visible label' if chosen else None}
    answer = {'properties': value, 'title': 'VisibleShelfGlance', 'type': 'object'} if wrapped else value
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if mode == 'json_schema':
            wire = body['response_format']['json_schema']['schema']
            assert set(wire['required']) == {'product', 'number', 'interest'}
            assert wire['properties']['number']['enum'] == [0, 1, 2]
            assert wire['properties']['interest']['minimum'] == 0
            assert wire['properties']['interest']['maximum'] == 10
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/wrapped-values', api_base='http://127.0.0.1:8081/v1',
                structured_output=mode, cache_dir=str(tmp_path), max_tokens=160, structured_sdk_retries=0))
            args = (schema, 'Choose from the shelf', 'Give actual values', view.data_url())
            first = await client.generate_structured_with_image_async(*args, max_retries=1)
            second = await client.generate_structured_with_image_async(*args, max_retries=1)
            assert first.model_dump() == second.model_dump() and client.get_usage().cached_requests == 1
            assert first.interest == (9 if chosen else 0)
            hit, _ = resolve(view, first)
            assert (hit.item.sku if hit else None) == ('B' if chosen else None)
            cached = json.loads(next(tmp_path.rglob('*.json')).read_text())['result']
            assert cached == {**value, 'reason': value['reason'] or ''}

    asyncio.run(exercise())
    assert len(calls) == 1


@pytest.mark.parametrize('payload', [
    {}, None, [], {'product': 'Banana', 'number': 2},
    {'product': 'Banana', 'number': 2, 'interest': {'type': 'integer', 'default': 9}},
    {'product': {'type': 'string', 'default': 'Banana'}, 'number': 2, 'interest': 9},
    {'product': 'Banana', 'number': {'enum': [2]}, 'interest': 9},
    {'product': 'Banana', 'number': 2, 'interest': True},
    {'product': 'Banana', 'number': True, 'interest': 9},
    {'product': 'Banana', 'number': 2, 'interest': -1},
    {'product': 'Banana', 'number': 2, 'interest': 11},
    {'product': 'Banana', 'number': 2, 'interest': None},
    {'product': 'Banana', 'number': 2, 'interest': '9'},
    {'product': '', 'number': 0, 'interest': 9},
    {'product': 'Invented product', 'number': 9999, 'interest': 9},
    {'properties': {'product': 'Banana', 'number': 2, 'interest': 9}},
])
def test_wrapping_does_not_make_invalid_measurements_valid(shelf, payload):
    schema = shelf_glance_model(shelf[1])
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({'properties': payload}), strict=True)


def test_root_choice_wins_over_a_conflicting_wrapper(shelf):
    schema = shelf_glance_model(shelf[1])
    answer = schema.model_validate_json(json.dumps({'product': '', 'number': 0, 'interest': 0,
        'properties': {'product': 'Banana', 'number': 2, 'interest': 9}}), strict=True)
    assert answer.interest == 0 and resolve(shelf[1], answer)[0] is None
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({'reason': 'Root fields present',
            'properties': {'product': 'Banana', 'number': 2, 'interest': 9}}), strict=True)


@pytest.mark.parametrize('numbered,product,number,accepted', [
    (False, '', 2, False), (False, 'Banana', 2, True), (True, '', 2, True),
])
def test_wrapped_targets_keep_raw_photo_and_numbered_chart_rules(shelf, numbered, product, number, accepted):
    schema = shelf_glance_model(shelf[1], numbered=numbered)
    payload = json.dumps({'properties': {'product': product, 'number': number, 'interest': 8}})
    if not accepted:
        with pytest.raises(ValidationError):
            schema.model_validate_json(payload, strict=True)
    else:
        answer = schema.model_validate_json(payload, strict=True)
        assert resolve(shelf[1], answer)[0].item.sku == 'B'
