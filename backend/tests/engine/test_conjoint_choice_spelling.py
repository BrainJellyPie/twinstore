"""Known option spellings must preserve every task in a conjoint response."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ConjointAttribute
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.conjoint import Coding, choice_model, conjoint_panel, none_share
from tests.engine.test_survey_model_price_bounds import PERSON


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('options', [2, 3, 4])
@pytest.mark.parametrize('none_option', [False, True])
@pytest.mark.parametrize('tasks', [3, 8, 15])
@pytest.mark.parametrize('padded', [False, True])
def test_canonical_choices_preserve_tasks_estimation_input_and_cache(monkeypatch, tmp_path,
                                                                  mode, options, none_option, tasks, padded):
    labels = list('ABCD'[:options]) + (['none'] if none_option else [])
    expected = [labels[i % len(labels)] for i in range(tasks)]
    raw = [f'\u3000{label.swapcase()}\t' if padded else label.swapcase() for label in expected]
    payload = {f'task_{i + 1}': choice for i, choice in enumerate(raw)} | {'why': None}
    calls, original = [], llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/conjoint-spelling',
                api_base='http://127.0.0.1:8081/v1', structured_output=mode, cache_dir=str(tmp_path)))
            args = (client, [PERSON], [ConjointAttribute(name='Style', levels=['Regular', 'Decaf'])], [100, 200])
            settings = dict(product='Tea', tasks=tasks, options=options, none_option=none_option, seed=7)
            people = await conjoint_panel(*args, **settings)
            assert len(people) == 1 and not people[0].error and people[0].why == ''
            choices = [None if label == 'none' else 'ABCD'.index(label) for label in expected]
            assert [task.choice for task in people[0].tasks] == choices
            x, y, owner = Coding([2], [100, 200], none_option).matrix(people)
            assert x.shape[:2] == (tasks, options + int(none_option))
            assert y.tolist() == [options if choice is None else choice for choice in choices]
            assert owner.tolist() == [0] * tasks
            assert none_share(people) == round(choices.count(None) / tasks, 4)
            path, = tmp_path.rglob('*.json')
            entry = json.loads(path.read_text())
            assert [entry['result'][f'task_{i + 1}'] for i in range(tasks)] == expected
            entry['result'].update(payload)
            path.write_text(json.dumps(entry))
            assert await conjoint_panel(*args, **settings) == people
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            schema = choice_model(tasks, options, none_option).model_json_schema()
            assert schema['required'] == [f'task_{i + 1}' for i in range(tasks)]
            assert schema['properties']['task_1']['enum'] == labels

    asyncio.run(exercise())


@pytest.mark.parametrize('none_option', [False, True])
@pytest.mark.parametrize('bad', [None, '', ' ', 'C', 'A/B', 'Option A', 0, False, [], {}])
def test_invalid_or_unoffered_choices_are_not_guessed(none_option, bad):
    schema = choice_model(3, 2, none_option)
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({'task_1': 'a', 'task_2': bad, 'task_3': 'b'}), strict=True)
    with pytest.raises(ValidationError):
        schema.model_validate_json('{"task_1":"a","task_3":"b"}', strict=True)


@pytest.mark.parametrize('choice', ['none', 'NONE', ' None\t'])
def test_forced_choice_does_not_invent_a_no_purchase_option(choice):
    with pytest.raises(ValidationError):
        choice_model(1, 2, False).model_validate_json(json.dumps({'task_1': choice}), strict=True)
