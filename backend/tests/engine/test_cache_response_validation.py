"""Cached model responses must meet the same JSON contract as fresh responses."""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Face, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _intent, _persona


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('ordering', ['planned', 'nearest'])
@pytest.mark.parametrize('field,value', [('quantity', True), ('quantity', False), ('quantity', '2'),
    ('quantity', 2.0), ('dwell', '6'), ('target', [True, 0]), ('target', ['1', 0]), ('area', ['0', 0, 2, 2])])
def test_invalid_cached_action_types_refetch_instead_of_changing_a_purchase(
    monkeypatch, tmp_path, collision_store, mode, ordering, field, value,
):
    calls = []
    original = llm_client.litellm.acompletion
    good = _intent().model_dump(mode='json')

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(good)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/cache-response-validation',
                api_base='http://127.0.0.1:8081/v1', structured_output=mode, cache_dir=str(tmp_path)))
            args = (IntentResponse, 'Plan a visit', 'Buy three items')
            first = await client.generate_structured_async(*args)
            path, = tmp_path.rglob('*.json')
            saved = json.loads(path.read_text())
            saved['result']['actions'][2][field] = value
            # The same body could not have passed the fresh Instructor response boundary.
            with pytest.raises(ValidationError):
                IntentResponse.model_validate_json(json.dumps(saved['result']), strict=True)
            path.write_text(json.dumps(saved))
            second = await client.generate_structured_async(*args)
            engine = PatternIntentImpulseEngine(_ScriptedLLM(second, ImpulseResponse()), AStarPathFinder(),
                SimulationConfig(route_ordering=ordering, budget_tolerance=None))
            decision = await engine.decide_actions(_context(collision_store, _persona()))
            result = execute_decision(collision_store, 'P1', Weekday.MON, '12:00:00', decision, AStarPathFinder(), 1)
            assert result.total_spent == 300 and result.purchases[0].quantity == 3
            assert second.model_dump() == first.model_dump() and len(calls) == 2
            assert (await client.generate_structured_async(*args)).model_dump() == first.model_dump()
            assert len(calls) == 2 and client.get_usage().cached_requests == 1
            assert json.loads(path.read_text())['result'] == first.model_dump(mode='json')

    asyncio.run(exercise())


class TypedAnswer(BaseModel):
    count: int
    enter: bool
    position: tuple[int, int]
    face: Face
    time: datetime
    price: Decimal


@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('field,value', [('count', '9'), ('count', True), ('enter', 'false'),
                                        ('position', ['3', 4]), ('valid', None)])
def test_sync_and_async_cache_keep_json_native_types_without_permissive_coercion(
    monkeypatch, tmp_path, asynchronous, field, value,
):
    expected = TypedAnswer(count=3, enter=True, position=(3, 4), face=Face.N,
                          time=datetime(2026, 10, 25, tzinfo=timezone.utc), price=Decimal('2.49'))
    client = llm_client.LiteLLMClient(LLMConfig(model='openai/local', api_base='http://127.0.0.1:9/v1',
                                             cache_dir=str(tmp_path)))
    messages, _ = client._messages('system', 'request')
    path = client._cache_path(TypedAnswer, messages, None)
    client._cache_put(path, expected)
    entry = json.loads(path.read_text())
    if field != 'valid':
        entry['result'][field] = value
        path.write_text(json.dumps(entry))
    calls = []

    def create(*args):
        calls.append(args)
        return expected, SimpleNamespace(usage=None)

    async def acreate(*args):
        return create(*args)

    monkeypatch.setattr(client, '_create', create)
    monkeypatch.setattr(client, '_acreate', acreate)
    for _ in range(2):
        answer = (asyncio.run(client.generate_structured_async(TypedAnswer, 'system', 'request')) if asynchronous
                  else client.generate_structured(TypedAnswer, 'system', 'request'))
        assert answer == expected
    assert len(calls) == int(field != 'valid')
    assert client.get_usage().cached_requests == (2 if field == 'valid' else 1)
