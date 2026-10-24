"""Reject unusable OCR numbers while model validation can still retry, before caching."""

import asyncio
import copy
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.vision_inputs import vlm_receipt


@pytest.mark.parametrize('field', ['quantity', 'unit_price', 'line_total', 'total'])
@pytest.mark.parametrize('number', ['NaN', 'Infinity', '-Infinity'])
@pytest.mark.parametrize('recovers', [True, False])
def test_invalid_receipt_numbers_retry_before_conversion_and_never_poison_cache(
    tmp_path, monkeypatch, field, number, recovers,
):
    good = {'currency': 'USD', 'total': 4.98, 'lines': [
        {'name': 'Tea', 'quantity': 2, 'unit_price': 2.49, 'line_total': 4.98}]}
    bad = copy.deepcopy(good)
    (bad if field == 'total' else bad['lines'][0])[field] = number
    requests = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            requests.append(json.loads(request.content))
            payload = good if recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={
                'id': 'offline-receipt', 'object': 'chat.completion', 'created': 0, 'model': 'local-model',
                'choices': [{'index': 0, 'finish_reason': 'stop',
                             'message': {'role': 'assistant', 'content': json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key='offline-test', base_url='http://local.invalid/v1',
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, 'client': transport, 'api_key': 'offline-test', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/local-receipt-validation',
                api_base='http://local.invalid/v1', structured_output='json_schema', cache_dir=str(tmp_path), seed=0))
            with Image.new('RGB', (2, 2)) as photo:
                if not recovers:
                    with pytest.raises(InstructorRetryException):
                        await vlm_receipt(client, photo, receipt_id='r1')
                    assert not list(tmp_path.rglob('*.json'))
                    return
                first = await vlm_receipt(client, photo, receipt_id='r1')
                again = await vlm_receipt(client, photo, receipt_id='r2')
                assert first.total == again.total == 498
                assert first.lines[0].quantity == 2 and first.lines[0].unit_price == 249
                assert first.lines[0].line_total == 498
                assert first.receipt_id == 'r1' and again.receipt_id == 'r2'
                assert client.get_usage().cached_requests == 1
                saved = [json.loads(p.read_text())['result'] for p in tmp_path.rglob('*.json')]
                assert len(saved) == 1 and saved[0]['total'] == 4.98

    asyncio.run(exercise())
    assert len(requests) == 2


@pytest.mark.parametrize('currency,minor', [('USD', 249), ('KRW', 2)])
def test_finite_negative_zero_and_unknown_receipt_amounts_remain_reviewable(currency, minor):
    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            return schema.model_validate({'currency': currency, 'total': 0, 'lines': [
                {'name': 'Return', 'quantity': -1, 'unit_price': 2.49, 'line_total': -2.49},
                {'name': 'Unknown', 'quantity': 0, 'unit_price': None, 'line_total': None}]})

    with Image.new('RGB', (2, 2)) as photo:
        receipt = asyncio.run(vlm_receipt(Model(), photo, receipt_id='review'))
    assert receipt.total == 0 and receipt.lines[0].quantity == -1
    assert receipt.lines[0].unit_price == minor and receipt.lines[0].line_total == -minor
    assert receipt.lines[1].quantity == 0 and receipt.lines[1].unit_price is None
