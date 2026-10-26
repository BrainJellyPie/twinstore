"""Serving/reference quantities cannot override a package's observed net size."""
import asyncio
import json

import pytest
from PIL import Image

from store_emulator.engine.package_reader import read_pack


@pytest.mark.parametrize('printed,size,name,supported', [
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '500 ml', 'Leafy Green Tea 100 ml', False),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '500 ml', 'Leafy Green Tea 500 ml', True),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '500 ml', 'Green Tea 100 ml Leafy', False),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '500 ml', 'Green Tea 500 ml Leafy', True),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '500 ml', 'Leafy Green Tea', True),
    ('ＬＥＡＦＹ ＧＲＥＥＮ ＴＥＡ ＮＥＴ ５００ｍｌ ＰＥＲ １００ｍｌ', '500ml', 'Leafy Green Tea 100 ml', False),
    ('LEAFY GREEN TEA NET 500 ml SERVING 100 ml', '500 ml', 'Leafy Green Tea 100 ml', False),
    ('LEAFY GREEN TEA NET 0.5 L PER 0.1 L', '0.5 L', 'Leafy Green Tea 0.1 L', False),
    ('LEAFY GREEN TEA NET 0,5 L PER 0,1 L', '0,5 L', 'Leafy Green Tea 0,1 L', False),
    ('LEAFY GREEN TEA NET 500 ml 500.0 ml PER 100 ml', '500 ml', 'Leafy Green Tea 500.0 ml', True),
    ('LEAFY GREEN TEA NET 0.5 L 0,5 L PER 0.1 L', '0.5 L', 'Leafy Green Tea 0,5 L', True),
    ('LEAFY GREEN TEA NET 500 g PER 100 g', '500 g', 'Leafy Green Tea 100 g', False),
    ('LEAFY GREEN TEA NET 500 g PER 100 g', '500 g', 'Leafy Green Tea 500 g', True),
    ('LEAFY GREEN TEA NET 16 oz PER 2 oz', '16 oz', 'Leafy Green Tea 2 oz', False),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '500 ml', 'Leafy Green Tea 500 ml 100 ml', False),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '', 'Leafy Green Tea 100 ml', True),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', None, 'Leafy Green Tea 100 ml', True),
    ('LEAFY GREEN TEA NET 500 ml PER 100 ml', '900 ml', 'Leafy Green Tea 100 ml', True),
    ('LEAFY GREEN TEA NET 500 ml 0.5 L PER 100 ml', '500 ml', 'Leafy Green Tea 0.5 L', True),
    ('LEAFY GREEN TEA NET 500 ml 6 PACK PER 100 ml', '500 ml', 'Leafy Green Tea 6 pack', True),
    ('LEAFY GREEN TEA NET 500 ml 6 PACK PER 100 ml', '500 ml', 'Leafy Green Tea 100 ml 6 pack', False),
    ('LEAFY GREEN TEA NET 6 x 500 ml PER 100 ml', '6 x 500 ml', 'Leafy Green Tea 6 x 500 ml', True),
])
def test_conflicting_net_size_is_filtered_before_matching(printed, size, name, supported):
    calls = []

    class Model:
        async def generate_structured_with_image_async(self, schema, system, user, image, **kwargs):
            return schema(printed_text=printed, name='Green Tea', size=size, confidence=1)

        async def generate_structured_async(self, schema, system, user, **kwargs):
            context = json.loads(user)
            calls.append(context['store_products'])
            return schema(shelf_product=name)

    with Image.new('RGB', (2, 2)) as image:
        result = asyncio.run(read_pack(Model(), image, [name]))
    assert result.shelf_product == (name if supported else '')
    assert calls == ([[name]] if supported else [])


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('has_correct_product', [False, True])
@pytest.mark.parametrize('malicious_match', [False, True])
def test_net_size_filter_survives_wire_modes_and_cached_observations(monkeypatch, tmp_path, mode, has_correct_product, malicious_match):
    import httpx
    from openai import AsyncOpenAI
    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine import llm_client

    correct, wrong = 'Leafy Green Tea 500 ml', 'Leafy Green Tea 100 ml'
    products = [wrong, correct] if has_correct_product else [wrong]
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        user = next(message['content'] for message in body['messages'] if message['role'] == 'user')
        if isinstance(user, list):
            payload = dict(printed_text='LEAFY GREEN TEA NET 500 ml PER 100 ml', name='Green Tea',
                           brand='Leafy', size='500 ml', category='Tea', confidence=1)
        else:
            assert json.loads(user)['store_products'] == [correct]
            if mode == 'json_schema':
                assert body['response_format']['json_schema']['schema']['properties']['shelf_product']['enum'] == ['', correct]
            payload = {'shelf_product': wrong if malicious_match else correct}
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/net-size', api_base='http://127.0.0.1:8081/v1',
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new('RGB', (2, 2)) as image:
                result = await read_pack(client, image, products)
                assert result.shelf_product == (correct if has_correct_product and not malicious_match else '')
                assert result.size == '500 ml'
                assert (await read_pack(client, image, products)).model_dump() == result.model_dump()
                assert len(calls) == 1 + has_correct_product
                # A new catalog reuses the image read without restoring its old link.
                assert (await read_pack(client, image, [wrong])).shelf_product == ''
                assert len(calls) == 1 + has_correct_product

    asyncio.run(exercise())
