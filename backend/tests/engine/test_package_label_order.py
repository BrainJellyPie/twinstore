"""Catalog display order must not erase words actually observed on a label."""
import asyncio
import json

from PIL import Image
import pytest

from store_emulator.engine.package_reader import read_pack


@pytest.mark.parametrize('printed,name,supported', [
    ('LEAFY GREEN TEA 500 ml', 'Green Tea 500 ml — Leafy', True),
    ('LEAFY 500 ml GREEN TEA', 'Leafy Green Tea 500 ml', True),
    ('ＬＥＡＦＹ　ＧＲＥＥＮ　ＴＥＡ　５００ｍｌ', 'Green Tea 500 ml (Leafy)', True),
    ('LEAFY GREEN TEA 500 ml', '500ml Leafy Green Tea', True),
    ('LEAFY GREEN TEA 500 ml', 'Leafy Black Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml', 'Leafy Green Tea 50 ml', False),
    ('LEAFY GREEN TEA 500 ml', 'Leafy Green Tea 500 g', False),
    ('LEAFY GREEN TEA 500 ml', 'Green Green Tea 500 ml Leafy', False),
    ('LEAFY GREEN TEA 500 g 100 ml', 'Green Tea 500 ml Leafy', False),
    ('LEAFY GREEN TEA 500 g 100 ml', 'Green Tea 100 g Leafy', False),
    ('LEAFY GREEN TEA 500 g 100 ml', 'Green Tea 100 ml Leafy', True),
    ('ICECREAM 500 ml', 'Cream 500 ml', False),
    ('有機緑茶 500 ml', '緑茶 500 ml', False),
])
def test_package_candidates_keep_observed_words_across_display_orders(printed, name, supported):
    matched = []

    class Model:
        async def generate_structured_with_image_async(self, schema, system, user, image, **kwargs):
            assert name not in user
            return schema(printed_text=printed, name='Observed drink', confidence=1)

        async def generate_structured_async(self, schema, system, user, **kwargs):
            context = json.loads(user)
            matched.append(context['store_products'])
            assert context['store_products'] == [name]
            return schema(shelf_product=name)

    products = ['Unprinted brand 500 ml', name, 'Leafy Green Tea 1 L']
    with Image.new('RGB', (2, 2)) as image:
        reading = asyncio.run(read_pack(Model(), image, products))
    assert matched == ([[name]] if supported else [])
    assert reading.shelf_product == (name if supported else '')
    assert reading.name == 'Observed drink'
