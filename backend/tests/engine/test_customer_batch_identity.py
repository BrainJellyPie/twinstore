"""Different customer batches cannot masquerade as fresh samples through cache reuse."""

import asyncio
import hashlib
import json
import re

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('workflow', ['direct', 'probe_all', 'probe_sample', 'probe_short'])
@pytest.mark.parametrize('recovery', ['fits', 'context', 'length'])
@pytest.mark.parametrize('batch_size', [2, 5])
def test_distinct_batch_and_split_positions_preserve_sample_identity(monkeypatch, tmp_path,
                                                                  mode, workflow, recovery, batch_size):
    original = llm_client.litellm.acompletion
    requests, completed = [], []
    count = batch_size if workflow == 'probe_short' else 3 * batch_size
    shorten_remaining = (1 if recovery == 'fits' else 2) if workflow == 'probe_short' else 0
    profile = gen.TradeAreaProfile(keywords=[], identities=['resident'], purposes=['shopping'])
    hours = [gen.HourlyProfile(hour=9, visitor_count=count, person_types=['resident'])]

    def respond(request):
        nonlocal shorten_remaining
        body = json.loads(request.content)
        if mode == 'json_schema':
            schema = body['response_format']['json_schema']['schema']
        else:
            system = next(m['content'] for m in reversed(body['messages']) if m['role'] == 'system')
            schema = json.JSONDecoder().raw_decode(system.rsplit('matching this schema:', 1)[-1].lstrip())[0]
        fields = schema['properties']
        finish = 'stop'
        if 'identities' in fields:
            payload = profile.model_dump()
        elif 'hourly_profiles' in fields:
            payload = {'hourly_profiles': [row.model_dump() for row in hours]}
        else:
            prompt = next(m['content'] for m in body['messages'] if m['role'] == 'user' and '페르소나' in m['content'])
            requested = re.findall(r'^\[\d+\] (\d+)시', prompt, re.MULTILINE)
            requests.append(prompt)
            # No provider seed support: the prompt must separate independent samples.
            assert 'seed' not in body
            oversized = recovery != 'fits' and len(requested) > (batch_size + 1) // 2
            if oversized and recovery == 'context':
                return httpx.Response(400, request=request, json={'error': {'type': 'exceed_context_size_error',
                    'message': 'request (9000 tokens) exceeds the available context size (8192 tokens)'}})
            if oversized:
                finish = 'length'
                payload = {'personas': []}
            else:
                completed.append(prompt)
                if shorten_remaining:
                    requested = requested[:1]
                    shorten_remaining -= 1
                identity = hashlib.sha256(prompt.encode()).hexdigest()[:12]
                payload = {'personas': [dict(identity='resident', purpose='shopping', age_group='30s', gender='Female',
                    description=f'Sample {identity}, person {i}', intent='Buy groceries') for i in range(len(requested))]}
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': finish,
                'message': {'role': 'assistant', 'content': json.dumps(payload)}}]})

    async def exercise():
        nonlocal shorten_remaining
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/customer-batch-identity',
                api_base='http://127.0.0.1:8081/v1', structured_output=mode, cache_dir=str(tmp_path)))
            plans = []

            async def decide(plan):
                plans.append(plan)
                return plan.sample.per_day if workflow == 'probe_sample' else plan.all.per_day

            async def generate(seed):
                if workflow == 'direct':
                    return await gen.generate_personas_for_day(client, 'offline', profile, Weekday.MON, hours,
                        batch_size=batch_size, max_concurrent=1, seed=seed)
                return await gen.generate_batched(client, 'offline', 'Residents',
                    [DaySchedule(day=1, open_hour=9, close_hour=10)], batch_size=batch_size, max_concurrent=1,
                    seed=seed, decide=decide, pace=lambda usual: gen.Pace(count, batch_size, 2 * batch_size))

            first = await generate(42)
            written = [p for p in first if not p.twin_of]
            expected = 2 * batch_size if workflow == 'probe_sample' else count
            assert len(first) == count and len(written) == expected
            assert len({p.description for p in written}) == expected
            assert len({p.id for p in first}) == count and all(p.arrival_hour == 9 for p in first)
            if plans:
                plan = plans[0].sample if workflow == 'probe_sample' else plans[0].all
                assert plan.customers == expected
                assert plan.requests == 1 + -(-(expected - plans[0].probe_customers) // batch_size)
            before = len(completed)
            assert await generate(42) == first and len(completed) == before
            shorten_remaining = (1 if recovery == 'fits' else 2) if workflow == 'probe_short' else 0
            changed = await generate(43)
            next_written = [p for p in changed if not p.twin_of]
            assert len({p.description for p in next_written}) == expected
            assert not {p.description for p in written} & {p.description for p in next_written}
            assert len(completed) == 2 * before

    asyncio.run(exercise())
