"""Wrapped values from the CPU model remain choices, never schema-derived clicks."""
import asyncio
import json
import random

import httpx
import pytest
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.online import ActionKind, BrowserState
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.browser import build_page, numbering, outline
from store_emulator.engine.online.policies import Memory, ModelPolicy, StepView
from store_emulator.engine.online.prompt import choice_model
from tests.engine.test_online_store import _shoppers, _site


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('vision', [False, True])
@pytest.mark.parametrize('wrapped', [False, True])
@pytest.mark.parametrize('action', [ActionKind.SEARCH, ActionKind.LEAVE])
def test_sdk_choice_and_cache_keep_values_and_action(monkeypatch, tmp_path, mode, vision, wrapped, action):
    site = _site(welcome_popup='none')
    shopper = _shoppers(site, 1)[0]
    state = BrowserState()
    page = build_page(site, state)
    numbers = numbering(page, 37)
    target = next(control for control in page.active if control.action.kind == action)
    value = {'option': numbers[target.index], 'search_text': 'green tea' if action == ActionKind.SEARCH else '',
             'thought': 'Find tea' if action == ActionKind.SEARCH else 'Leave this shop'}
    answer = {'properties': value} if wrapped else value
    calls = []

    async def send(self, request, *args, **kwargs):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion',
            'created': 0, 'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(answer)}}]})

    monkeypatch.setattr(httpx.AsyncClient, 'send', send)
    client = LiteLLMClient(LLMConfig(model='openai/wrapped-choice', api_base='http://127.0.0.1:8081/v1',
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path), max_tokens=240))
    policy = ModelPolicy(client, vision=vision)
    view = StepView(page, state, numbers, outline(page, site), image_url='data:image/png;base64,AA==', seed=123)

    async def exercise():
        for _ in range(2):
            chosen = await policy.choose(site, shopper, view, Memory(), random.Random(7))
            assert chosen.source == 'model' and not chosen.error
            assert chosen.control == target and chosen.query == value['search_text']
            assert chosen.thought == value['thought']

    asyncio.run(exercise())
    assert policy.answered == 2 and policy.failed == 0
    assert len(calls) == 1 and client.get_usage().cached_requests == 1
    cached = [json.loads(p.read_text())['result'] for p in tmp_path.glob('*/*.json')]
    assert cached == [value]


@pytest.mark.parametrize('payload', [
    None, [], {}, {'thought': 'Leave'}, {'option': None}, {'option': True}, {'option': False},
    {'option': {'type': 'integer', 'default': 1}}, {'option': {'enum': [1]}},
    {'option': 4}, {'option': -1}, {'option': 3}, {'option': 3, 'search_text': '  '},
    {'option': 3, 'search_text': {'type': 'string', 'default': 'tea'}},
    {'properties': {'option': 1}},
])
def test_wrapper_does_not_bypass_required_values_or_page_validation(payload):
    with pytest.raises(ValidationError):
        choice_model([1, 3, 9], search_number=3).model_validate_json(json.dumps({'properties': payload}), strict=True)


def test_root_choice_has_priority_and_partial_root_is_not_replaced():
    schema = choice_model([1, 3, 9], search_number=3)
    assert schema.model_validate({'option': 1, 'properties': {'option': 9}}).option == 1
    with pytest.raises(ValidationError):
        schema.model_validate({'option': 4, 'properties': {'option': 1}})
    with pytest.raises(ValidationError):
        schema.model_validate({'thought': 'Root answer', 'properties': {'option': 1}})


@pytest.mark.parametrize('option,thought', [
    (1, "I'm tired of waiting for a slow page load and want to finish the order quickly. "
        "I'm on a budget, so I'll just close the tab and go to the next one."),
    (9, "I'm tired of waiting for a coupon code. I just bought a shirt, so I need to finish "
        "the order. I'll click the 'Place order' button."),
])
def test_actual_cpu_wrapped_choice_preserves_the_selected_number(option, thought):
    # CPU JSON-mode traces from checkout: mobile chose 1, desktop chose 9.
    value = {'properties': {'thought': thought, 'option': option, 'search_text': ''}}
    result = choice_model(list(range(1, 10)), search_number=3).model_validate_json(json.dumps(value), strict=True)
    assert result.option == option
    assert result.model_dump() == value['properties']
