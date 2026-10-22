import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.product_images import project_image_loader
from store_emulator.application.storage.images import layout_image_url, load_manifest, save_image
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, setup_path
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.layout_gen.catalog import CATALOG, CATALOG_IMAGE_URLS, catalog_slot_item
from store_emulator.engine.perception.product_images import default_product_image
from store_emulator.engine.perception.shelf_render import render_face

PICTURED = [p for products in CATALOG.values() for p in products if catalog_slot_item(p, 'USD').image_url]
PID = 'proj_oldphotos'


@pytest.mark.parametrize('product', PICTURED, ids=lambda p: p.en)
@pytest.mark.parametrize('currency', ['USD', 'KRW', 'JPY'])
def test_saved_catalog_skus_get_new_photos_without_replacing_product_values(product, currency):
    item = catalog_slot_item(product, currency)
    expected = item.image_url
    item.image_url = None
    item.name = 'My renamed product'
    item.price += 123
    before = item.model_dump()
    assert layout_image_url(PID, item.sku, None, {}) == expected
    assert default_product_image(item) is not None
    assert item.model_dump() == before


def test_unknown_sku_does_not_borrow_a_picture_by_name():
    item = SlotItem(sku='custom', name='Milk 1L', price=100)
    assert layout_image_url(PID, item.sku, None, {}) is None
    assert default_product_image(item) is None
    assert 'custom' not in CATALOG_IMAGE_URLS


def test_explicit_and_uploaded_photos_stay_ahead_of_catalog_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / '.data' / PID / 'metadata.json', {'name': 'Old photos'})
    item = catalog_slot_item(PICTURED[0], 'USD')
    custom = '/custom/product.png'
    assert layout_image_url(PID, item.sku, custom, {}) == custom
    buf = io.BytesIO(); Image.new('RGB', (40, 60), 'red').save(buf, format='PNG')
    save_image(PID, item.sku, buf.getvalue(), 'photo.png')
    manifest = load_manifest(PID)
    item.image_url = None
    assert layout_image_url(PID, item.sku, None, manifest).startswith(f'/api/projects/{PID}/images?')
    assert project_image_loader(PID)(item).getpixel((0, 0)) == (255, 0, 0, 255)
    frozen = f'/api/projects/{PID}/product-photo-files/' + 'a' * 64
    assert layout_image_url(PID, item.sku, frozen, manifest) == frozen


def test_old_setup_read_and_vlm_preview_gain_photos_without_rewriting_disk(tmp_path, monkeypatch):
    import base64
    from store_emulator.server.main import app
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / '.data' / PID / 'metadata.json', {'name': 'Old photos', 'currency': 'USD'})
    item = catalog_slot_item(PICTURED[0], 'USD')
    expected_url = item.image_url
    item.image_url = None
    item.name = 'Preserve this label'; item.price = 777
    rack = Rack(id='old-rack', type='shelf', shape=[[1]], position=(2, 2),
                slots=[Slot(block=0, face=Face.S, level=3, items=[item])])
    store = Store(id='old', name='Old store', type='general', currency='USD', grid_size=(8, 8), racks=[rack])
    path = setup_path(PID, 'setup_old')
    write_json(path, new_setup_data('Old', None, store.model_dump(mode='json')))
    before = path.read_bytes()
    client = TestClient(app)
    response = client.get(f'/api/projects/{PID}/setups/setup_old')
    assert response.status_code == 200, response.text
    product = response.json()['store']['racks'][0]['slots'][0]['items'][0]
    assert product['image_url'] == expected_url
    assert (product['name'], product['price'], product['sku']) == (item.name, item.price, item.sku)
    preview = client.post(f'/api/projects/{PID}/shelf-tests/preview', json={'setup_id': 'setup_old', 'rack_id': rack.id, 'face': 'S'})
    assert preview.status_code == 200, preview.text
    actual = base64.b64decode(preview.json()['control'].split(',', 1)[1])
    assert actual != render_face(rack, Face.S, width=640, number_on_tag=False, image_loader=lambda item: None).png
    assert actual == render_face(rack, Face.S, width=640, number_on_tag=False).png
    assert path.read_bytes() == before
