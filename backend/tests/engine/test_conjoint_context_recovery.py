"""Oversized conjoint prompts split existing tasks without resampling the design."""

import asyncio
import json
import random
import re

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, InstructorRetryException
from litellm.exceptions import BadRequestError
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ConjointAttribute
from store_emulator.domain.types import stable_seed
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.conjoint import Coding, conjoint_panel, design, tasks_text
from tests.engine.test_survey_model_price_bounds import PERSON


ATTRIBUTES = [ConjointAttribute(name='Ingredients', levels=['Organic', 'Regular']),
              ConjointAttribute(name='Storage', levels=['Chilled', 'Shelf stable'])]
MESSAGE = 'request (10000 tokens) exceeds the available context size (8192 tokens)'


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('none_option', [False, True])
@pytest.mark.parametrize('tasks,capacity', [(3, 2), (8, 4), (15, 4), (15, 15)])
@pytest.mark.parametrize('concurrency', [1, 2])
def test_http_recovery_preserves_each_persons_full_design_choices_and_cache(
    monkeypatch, tmp_path, mode, none_option, tasks, capacity, concurrency,
):
    people = [PERSON.model_copy(update={'id': f'p{i}', 'identity': f'Respondent {i}'}) for i in range(2)]
    plans = {p.id: design([2, 2, 2], tasks, 4, random.Random(stable_seed('conjoint-design', 7, p.id))) for p in people}
    expected_text = {p.id: dict(re.findall(r'(Task \d+:)\n(.*?)(?=\n\nTask |$)',
        tasks_text(ATTRIBUTES, [100, 200], 'USD', plans[p.id], none_option), re.DOTALL)) for p in people}
    calls, completed, active, peak = [], [], 0, 0
    original = llm_client.litellm.acompletion

    async def respond(request):
        nonlocal active, peak
        body = json.loads(request.content)
        user = next(m['content'] for m in body['messages'] if m['role'] == 'user')
        person = next(p for p in people if p.identity in user)
        blocks = re.findall(r'(Task \d+:)\n(.*?)(?=\n\nTask |$)', user, re.DOTALL)
        indices = [int(re.search(r'\d+', title)[0]) for title, _ in blocks]
        calls.append((person.id, indices))
        for title, block in blocks:
            assert block == expected_text[person.id][title]
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0)
            if len(indices) > capacity:
                return httpx.Response(400, request=request, json={'error': {
                    'message': MESSAGE, 'type': 'exceed_context_size_error'}})
            completed.append((person.id, indices))
            choices = 'ABCD' + ('N' if none_option else '')
            payload = {f'task_{i}': ('none' if choices[(i - 1) % len(choices)] == 'N'
                                     else choices[(i - 1) % len(choices)]) for i in indices}
            payload['why'] = f'Choices for tasks {indices[0]} to {indices[-1]}.'
            return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
                'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': json.dumps(payload)}}]})
        finally:
            active -= 1

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/conjoint-context',
                api_base='http://127.0.0.1:8081/v1', structured_output=mode, cache_dir=str(tmp_path), max_tokens=600))
            args = (client, people, ATTRIBUTES, [100, 200])
            settings = dict(product='Tea', tasks=tasks, options=4, none_option=none_option, seed=7, max_concurrent=concurrency)
            result = await asyncio.wait_for(conjoint_panel(*args, **settings), timeout=5)
            assert len(result) == 2 and all(not row.error for row in result)
            expected = [None if none_option and i % 5 == 4 else i % (5 if none_option else 4) for i in range(tasks)]
            for row in result:
                assert [task.profiles for task in row.tasks] == plans[row.respondent]
                assert [task.choice for task in row.tasks] == expected
                leaves = [indices for pid, indices in completed if pid == row.respondent]
                assert sorted(i for indices in leaves for i in indices) == list(range(1, tasks + 1))
                assert all(f'Choices for tasks {indices[0]} to {indices[-1]}.' in row.why for indices in leaves)
            x, y, owners = Coding([2, 2], [100, 200], none_option).matrix(result)
            assert x.shape[:2] == (2 * tasks, 4 + int(none_option))
            assert y.tolist() == [4 if c is None else c for c in expected] * 2
            assert owners.tolist() == [0] * tasks + [1] * tasks
            before = len(completed)
            assert await conjoint_panel(*args, **settings) == result and len(completed) == before
            assert client.get_usage().cached_requests == before
            assert len(list(tmp_path.rglob('*.json'))) == before
            if tasks <= capacity:
                assert len(calls) == 2
            assert 1 <= peak <= concurrency

    asyncio.run(exercise())


def overflow():
    return BadRequestError(MESSAGE, model='openai/local', llm_provider='openai')


@pytest.mark.parametrize('failure', ['single_context', 'timeout', 'value', 'unrelated', 'last_timeout', 'child'])
def test_irreducible_or_unrelated_failures_do_not_publish_partial_respondents(failure):
    calls = []

    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            indices = [int(i) for i in re.findall(r'^Task (\d+):', prompt, re.MULTILINE)]
            calls.append(indices)
            if failure == 'single_context' or failure == 'child' and len(indices) > 2:
                raise overflow()
            if failure == 'timeout':
                raise TimeoutError(MESSAGE)
            if failure == 'value':
                raise ValueError(MESSAGE)
            if failure == 'unrelated':
                raise BadRequestError('Unsupported parameter', model='openai/local', llm_provider='openai')
            if failure == 'last_timeout':
                raise InstructorRetryException('retries exhausted', n_attempts=2, total_usage=0,
                    failed_attempts=[FailedAttempt(1, overflow()), FailedAttempt(2, TimeoutError('offline'))])
            if indices[-1] == 4:
                raise TimeoutError('Second child failed')
            return schema.model_validate({f'task_{i}': 'A' for i in indices})

    count = 1 if failure == 'single_context' else 4
    rows = asyncio.run(conjoint_panel(Model(), [PERSON], ATTRIBUTES, [100, 200], product='Tea', tasks=count))
    assert len(rows) == 1 and rows[0].error and all(task.choice is None for task in rows[0].tasks)
    assert len(calls) == (3 if failure == 'child' else 1)
