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
    ('LEAFY GREEN TEA 6 x 500 ml', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 6 x 500 ml', 'Leafy Green Tea', False),
    ('LEAFY GREEN TEA 6 x 500 ml', 'Leafy Green Tea 6 x 500 ml', True),
    ('LEAFY GREEN TEA 6×500ml', 'Leafy Green Tea 6 x 500 ml', True),
    ('LEAFY GREEN TEA 6*500ml', 'Leafy Green Tea 6 x 500 ml', True),
    ('ＬＥＡＦＹ ＧＲＥＥＮ ＴＥＡ ６Ｘ５００ｍｌ', 'Leafy Green Tea 6 x 500 ml', True),
    ('LEAFY GREEN TEA 2 x 6 x 500 ml', 'Leafy Green Tea 6 x 500 ml', False),
    ('LEAFY GREEN TEA 2 x 6 x 500 ml', 'Leafy Green Tea 2 x 6 x 500 ml', True),
    ('LEAFY GREEN TEA 6 x 500 ml', 'Leafy Green Tea 5 x 500 ml', False),
    ('LEAFY GREEN TEA 6 x 500 ml', 'Leafy Green Tea 6 x 100 ml', False),
    ('LEAFY GREEN TEA 6 x 500 g', 'Leafy Green Tea 6 x 500 ml', False),
    ('LEAFY 6 x 500 ml GREEN TEA', 'Green Tea 6 x 500 ml Leafy', True),
    ('LEAFY GREEN TEA 6 x 500 ml 6 x 500 ml', 'Leafy Green Tea 6 x 500 ml', True),
    ('LEAFY GREEN TEA 500 ml x 6', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml x 6', 'Leafy Green Tea', False),
    ('LEAFY GREEN TEA 500 ml x 6', 'Leafy Green Tea 500 ml x 6', True),
    ('LEAFY GREEN TEA 500 ml X6', 'Green Tea 500 ml x 6 Leafy', True),
    ('LEAFY GREEN TEA 500ml×6', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500ml×6', 'Leafy Green Tea 500 ml x 6', True),
    ('LEAFY GREEN TEA 500 ml * 6', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml * 6', 'Leafy Green Tea 500 ml x 6', True),
    ('ＬＥＡＦＹ ＧＲＥＥＮ ＴＥＡ ５００ｍｌ Ｘ６', 'Leafy Green Tea 500 ml', False),
    ('ＬＥＡＦＹ ＧＲＥＥＮ ＴＥＡ ５００ｍｌ Ｘ６', 'Leafy Green Tea 500 ml x 6', True),
    ('LEAFY GREEN TEA 0.5 L x 6', 'Leafy Green Tea 0.5 L', False),
    ('LEAFY GREEN TEA 0,5 L x 6', 'Leafy Green Tea 0,5 L x 6', True),
    ('LEAFY GREEN TEA 500 g x 6', 'Leafy Green Tea 500 g', False),
    ('LEAFY GREEN TEA 500 g x 6', 'Leafy Green Tea 500 ml x 6', False),
    ('LEAFY GREEN TEA 500 ml x 6', 'Leafy Green Tea 500 ml x 5', False),
    ('LEAFY GREEN TEA 500 ml x 6', 'Leafy Green Tea 100 ml x 6', False),
    ('LEAFY GREEN TEA 500 ml x 2 x 3', 'Leafy Green Tea 500 ml x 2', False),
    ('LEAFY GREEN TEA 500 ml x 2 x 3', 'Leafy Green Tea 500 ml x 2 x 3', True),
    ('LEAFY GREEN TEA 2 x 500 ml x 3', 'Leafy Green Tea 2 x 500 ml', False),
    ('LEAFY GREEN TEA 2 x 500 ml x 3', 'Leafy Green Tea 500 ml x 3', False),
    ('LEAFY GREEN TEA 2 x 500 ml x 3', 'Leafy Green Tea 2 x 500 ml x 3', True),
    ('LEAFY GREEN TEA 2 x 500 ml x 3', 'Green Tea 2 x 500 ml x 3 Leafy', True),
    ('LEAFY GREEN TEA 2 x 500 ml x 3 PER 2 x 500 ml', 'Leafy Green Tea 2 x 500 ml x 3', False),
    ('LEAFY GREEN TEA 500 ml x 6 500 ml x 6', 'Leafy Green Tea 500 ml x 6', True),
    ('LEAFY GREEN TEA 500 ml 6 PACK', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6 PACK', 'Leafy Green Tea 500 ml 6 pack', True),
    ('LEAFY GREEN TEA 500 ml 6-pack', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6 pk', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml PACK OF 6', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml PACK OF 6', 'Leafy Green Tea 500 ml pack of 6', True),
    ('LEAFY GREEN TEA 500 ml 6입', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6입', 'Leafy Green Tea 500 ml 6입', True),
    ('LEAFY GREEN TEA 500 ml 6本入り', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6本入り', 'Leafy Green Tea 500 ml 6本入り', True),
    ('LEAFY VITAMIN B6 PACK 500 ml', 'Leafy Vitamin B6 Pack 500 ml', True),
    ('LEAFY GREEN TEA 500 ml 6 packing tips', 'Leafy Green Tea 500 ml', True),
    ('LEAFY GREEN TEA 500 ml 6 BOTTLES', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6 BOTTLES', 'Leafy Green Tea 500 ml 6 bottles', True),
    ('LEAFY GREEN TEA 500 ml 6-bottle', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6 CANS', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6 CANS', 'Leafy Green Tea 500 ml 6 cans', True),
    ('LEAFY GREEN TEA 500 ml 6 JARS', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6병', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6병', 'Leafy Green Tea 500 ml 6병', True),
    ('LEAFY GREEN TEA 500 ml 6캔', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6本', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 6缶', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml ６ ＢＯＴＴＬＥＳ', 'Leafy Green Tea 500 ml', False),
    ('LEAFY GREEN TEA 500 ml 1 BOTTLE', 'Leafy Green Tea 500 ml', True),
    ('LEAFY GREEN TEA 500 ml 1 PACK', 'Leafy Green Tea 500 ml', True),
    ('LEAFY VITAMIN B6 BOTTLES 500 ml', 'Leafy Vitamin B6 Bottles 500 ml', True),
    ('LEAFY GREEN TEA 500 ml 6 bottled flavours', 'Leafy Green Tea 500 ml', True),
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
