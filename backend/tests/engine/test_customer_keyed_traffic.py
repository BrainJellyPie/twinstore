"""Numbered traffic entries end after the supplied slots and retain their clocks through caches."""
import asyncio
import json

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('window', [(0, 1), (23, 24), (9, 18), (0, 24)])
@pytest.mark.parametrize('reverse', [False, True])
def test_numbered_traffic_through_sdk_and_canonical_cache(monkeypatch, tmp_path, mode, window, reverse):
    opening, closing = window
    entries = {str(i): {'visitor_count': i % 3, 'person_types': ['동네 주민'] if i % 3 else []}
               for i in range(closing - opening)}
    if reverse:
        entries = dict(reversed(list(entries.items())))
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = {'hourly_profiles': entries}
        if mode == 'json_schema':
            schema = body['response_format']['json_schema']['schema']
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(payload)
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                'role': 'assistant', 'content': json.dumps(payload, ensure_ascii=False)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/numbered-traffic',
                api_base='http://127.0.0.1:8081/v1', structured_output=mode, cache_dir=str(tmp_path)))
            profile = gen.TradeAreaProfile(keywords=[], identities=['동네 주민'], purposes=[])
            args = (client, '서울', '동네 주민', profile, Weekday.MON, opening, closing)
            first = await gen.analyze_daily_traffic(*args)
            assert [row.hour for row in first] == list(range(opening, closing))
            assert [row.visitor_count for row in first] == [i % 3 for i in range(closing - opening)]
            assert await gen.analyze_daily_traffic(*args) == first
            assert len(calls) == client.get_usage().cached_requests == 1
            saved = [json.loads(p.read_text())['result'] for p in tmp_path.rglob('*.json')]
            assert saved == [{'hourly_profiles': [row.model_dump() for row in first]}]

    asyncio.run(exercise())


@pytest.mark.parametrize('fault', ['missing', 'extra', 'leading_zero', 'null', 'schema', 'clock', 'mixed_clock', 'bad_type'])
def test_numbered_entries_do_not_guess_positions_or_mixed_clocks(fault):
    entries = {str(i): dict(visitor_count=1, person_types=['resident']) for i in range(3)}
    if fault == 'missing': entries.pop('1')
    elif fault == 'extra': entries['3'] = entries['0'].copy()
    elif fault == 'leading_zero': entries['01'] = entries.pop('1')
    elif fault == 'null': entries['1'] = None
    elif fault == 'schema': entries = {'type': 'array', 'items': {'default': entries['0']}}
    elif fault == 'clock':
        for row in entries.values(): row['hour'] = 9
    elif fault == 'mixed_clock': entries['1']['hour'] = 10
    else: entries['1']['person_types'] = ['not a supplied identity']
    with pytest.raises(ValidationError):
        gen.traffic_response_model(9, 12, identities=['resident']).model_validate_json(
            json.dumps({'hourly_profiles': entries}), strict=True)


def test_shared_row_definition_stays_small_and_does_not_mutate_other_schemas():
    labels = [f'Resident {i} ' + 'x' * 105 for i in range(16)]
    cls = gen.traffic_response_model(0, 24, identities=labels)
    schema = cls.model_json_schema()
    slots = schema['properties']['hourly_profiles']
    assert slots['type'] == 'object' and slots['additionalProperties'] is False
    assert set(slots['required']) == {str(i) for i in range(24)}
    assert all(value == slots['properties']['0'] for value in slots['properties'].values())
    assert '$ref' in slots['properties']['0']
    # Repeating 16 long identity labels for every slot would overflow local context.
    assert len(json.dumps(schema, ensure_ascii=False)) < 6000
    assert 'hour' in gen.HourlyProfile.model_json_schema()['required']
    other = gen.traffic_response_model(23, 24, identities=['different'])
    payload = {'hourly_profiles': {'0': {'visitor_count': 1, 'person_types': ['different']}}}
    Draft202012Validator(other.model_json_schema()).validate(payload)
    assert cls.model_json_schema() == schema
