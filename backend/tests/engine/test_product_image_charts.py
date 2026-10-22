import io
import random

import pytest
from PIL import Image, ImageDraw

from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.layout_gen.catalog_expansion import PACKSHOT_URLS
from store_emulator.engine.perception.product_images import decode_product_image
from store_emulator.engine.perception import product_images
from store_emulator.engine.perception.shelf_render import render_face
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance, resolve


def rack_with(items):
    return Rack(id='rack', type='shelf', shape=[[1] * max(1, (len(items) + 3) // 4)], position=(1, 1), rack_name='Photo shelf',
                slots=[Slot(block=start // 4, face=Face.S, level=4, items=items[start:start + 4])
                       for start in range(0, len(items), 4)])


@pytest.mark.parametrize('name', PACKSHOT_URLS)
def test_every_catalog_photo_changes_actual_chart_pixels_without_changing_marks(name):
    product = next(p for values in CATALOG.values() for p in values if p.en == name)
    item = catalog_slot_item(product, 'USD')
    rack = rack_with([item])
    photographed = render_face(rack, Face.S, width=384, rng=random.Random(4))
    text = render_face(rack, Face.S, width=384, rng=random.Random(4), image_loader=lambda item: None)
    assert photographed.png != text.png
    assert [(m.mark, m.item.sku, m.item.price) for m in photographed.items] == [(m.mark, m.item.sku, m.item.price) for m in text.items]
    assert photographed.png == render_face(rack, Face.S, width=384, rng=random.Random(4)).png


@pytest.mark.parametrize('width', [128, 256, 384, 768])
@pytest.mark.parametrize('count', [0, 1, 2, 8, 32, 100])
def test_dense_grid_keeps_photos_names_prices_and_all_exact_numbers(width, count, monkeypatch):
    labels = []
    original = ImageDraw.ImageDraw.text
    def text(self, xy, text, *args, **kwargs):
        labels.append(text)
        return original(self, xy, text, *args, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', text)
    items = [SlotItem(sku=f'sku{i}', name=f'Item {i}', price=249, image_url='/local.png') for i in range(count)]
    photo = Image.new('RGBA', (60, 90), (17, 203, 171, 255))
    view = render_face(rack_with(items), Face.S, width=width, image_loader=lambda item: photo)
    assert view.size[0] == width
    assert [m.item.sku for m in view.items] == [p.sku for p in items]
    assert [m.mark for m in view.items] == list(range(1, count + 1))
    if count:
        with Image.open(io.BytesIO(view.png)) as image:
            assert sum(pixel == (17, 203, 171) for pixel in image.get_flattened_data()) > count * 10
        for i in range(count):
            assert f'Item {i}' in labels
            assert any(str(label).startswith(f'#{i+1} ') for label in labels)
        chosen, method = resolve(view, ShelfGlance(number=count))
        assert chosen is not None and chosen.item.sku == f'sku{count-1}' and method == 'number'


@pytest.mark.parametrize('data', [b'', b'not an image', b'GIF89a', b'x' * (10 * 1024 * 1024 + 1)])
def test_corrupt_or_oversized_images_fall_back(data):
    assert decode_product_image(data) is None


def test_transparency_and_exif_orientation_are_preserved():
    png = io.BytesIO()
    Image.new('RGBA', (40, 20), (255, 0, 0, 90)).save(png, format='PNG')
    transparent = decode_product_image(png.getvalue())
    assert transparent is not None and transparent.getpixel((0, 0)) == (255, 0, 0, 90)
    jpeg = io.BytesIO()
    exif = Image.Exif(); exif[274] = 6
    Image.new('RGB', (40, 20), 'blue').save(jpeg, format='JPEG', exif=exif)
    rotated = decode_product_image(jpeg.getvalue())
    assert rotated is not None and rotated.size == (20, 40)


def test_missing_file_and_empty_name_do_not_break_the_grid(tmp_path):
    item = SlotItem(sku='no-label', name='', price=0, image_url=(tmp_path / 'missing.png').as_uri())
    assert render_face(rack_with([item]), Face.S).items[0].item.sku == 'no-label'
    photo = Image.new('RGB', (100, 1), 'red')
    view = render_face(rack_with([item]), Face.S, image_loader=lambda item: photo)
    assert view.png


def test_bundled_product_itself_is_large_enough_to_see_in_the_vlm_grid(monkeypatch):
    raw = Image.new('RGB', (256, 384), 'white')
    ImageDraw.Draw(raw).rectangle((90, 150, 165, 235), fill=(193, 24, 45))
    data = io.BytesIO(); raw.save(data, format='PNG')
    monkeypatch.setattr(product_images, 'packshot', lambda sheet, index: data.getvalue())
    item = SlotItem(sku='fit-photo', name='Example', price=349,
                    image_url='/api/catalog-images/starter-999/0.webp')
    rack = rack_with([item])
    fitted = render_face(rack, Face.S, width=384)
    original = render_face(rack, Face.S, width=384, image_loader=lambda item: raw)
    def colored_pixels(view):
        with Image.open(io.BytesIO(view.png)) as image:
            return sum(r > 140 and g < 60 and b < 80 for r, g, b in image.get_flattened_data())
    assert colored_pixels(fitted) > 4 * colored_pixels(original)
    assert [(m.mark, m.item.sku, m.item.price) for m in fitted.items] == [(m.mark, m.item.sku, m.item.price) for m in original.items]


@pytest.mark.parametrize('color', ['white', (235, 235, 235), 'black'])
def test_light_or_blank_catalog_photo_does_not_vanish_when_margins_are_fitted(monkeypatch, color):
    raw = Image.new('RGB', (256, 384), 'white')
    ImageDraw.Draw(raw).rectangle((80, 120, 175, 263), fill=color)
    data = io.BytesIO(); raw.save(data, format='PNG')
    monkeypatch.setattr(product_images, 'packshot', lambda sheet, index: data.getvalue())
    index = 0 if color == 'white' else 1 if color == 'black' else 2
    picture = product_images.bundled_product_image(f'/api/catalog-images/starter-998/{index}.webp')
    assert picture is not None and min(picture.size) > 0
    assert picture.getpixel((picture.width // 2, picture.height // 2)) == raw.convert('RGBA').getpixel((128, 192))
    # General uploaded pictures keep their original framing; only the bundled atlas loader fits margins.
    decoded = decode_product_image(data.getvalue())
    assert decoded is not None and decoded.size == raw.size
