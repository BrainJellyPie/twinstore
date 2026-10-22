import io

import pytest
from PIL import Image

from store_emulator.application.product_images import project_image_loader
from store_emulator.application.storage.images import image_url_for, save_image
from store_emulator.application.storage.io import write_json
from store_emulator.domain.rack import SlotItem

PID = 'proj_chart'


def png(color):
    data = io.BytesIO(); Image.new('RGB', (40, 60), color).save(data, format='PNG'); return data.getvalue()


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / '.data' / PID / 'metadata.json', {'name': 'Chart'})
    return tmp_path


def test_uploaded_photo_overrides_builtin_but_reviewed_photo_keeps_its_identity(project):
    save_image(PID, 'sku / + 한글', png('red'), 'uploaded.png')
    loader = project_image_loader(PID)
    item = SlotItem(sku='sku / + 한글', name='Name', price=100, image_url='/api/catalog-images/starter-01/0.webp')
    assert loader(item).getpixel((0, 0)) == (255, 0, 0, 255)
    item.image_url = image_url_for(PID, item.sku)
    assert loader(item).getpixel((0, 0)) == (255, 0, 0, 255)
    digest = 'a' * 64
    path = project / '.data' / PID / 'product_photos' / f'{digest}.png'
    path.parent.mkdir(); path.write_bytes(png('blue'))
    item.image_url = f'/api/projects/{PID}/product-photo-files/{digest}'
    assert loader(item).getpixel((0, 0)) == (0, 0, 255, 255)


def test_image_cache_is_scoped_to_one_run_and_missing_image_can_be_added_later(project):
    item = SlotItem(sku='sku', name='Name', price=100)
    before = project_image_loader(PID)
    assert before(item) is None
    save_image(PID, item.sku, png('red'), 'a.png')
    first = project_image_loader(PID)
    assert first(item).getpixel((0, 0)) == (255, 0, 0, 255)
    save_image(PID, item.sku, png('blue'), 'b.png')
    assert first(item).getpixel((0, 0)) == (255, 0, 0, 255)
    assert project_image_loader(PID)(item).getpixel((0, 0)) == (0, 0, 255, 255)


def test_library_images_and_explicit_experiment_files_are_loaded(project):
    path = project / '.data' / PID / 'lab_assets' / 'pack.png'
    path.parent.mkdir(); path.write_bytes(png('lime'))
    save_image(PID, 'sku', png('red'), 'a.png')
    loader = project_image_loader(PID)
    for sku, url in [('other', f'/api/projects/{PID}/lab/packages/pack'), ('sku', path.as_uri())]:
        assert loader(SlotItem(sku=sku, name='Name', price=100, image_url=url)).getpixel((0, 0)) == (0, 255, 0, 255)


@pytest.mark.parametrize('url', [
    'https://example.test/product.png', '//example.test/product.png', 'file:///etc/passwd',
    '/api/projects/other/images?sku=x', '/api/projects/proj_chart/images?sku=x&sku=y',
    '/api/projects/proj_chart/lab/packages/../../metadata', '/api/projects/proj_chart/lab/packages/%2e%2e',
    '/api/projects/proj_chart/product-photo-files/../metadata', '/api/catalog-images/starter-01/99.webp',
    '/api/projects/proj_chart/images?sku=missing', '/api/projects/proj_chart/lab/packages/missing',
])
def test_unknown_foreign_or_unsafe_urls_do_not_replace_text_with_arbitrary_files(project, url):
    assert project_image_loader(PID)(SlotItem(sku='unknown', name='Name', price=100, image_url=url)) is None


def test_broken_local_image_is_a_text_fallback(project):
    path = project / '.data' / PID / 'lab_assets' / 'broken.png'; path.parent.mkdir(); path.write_bytes(b'broken')
    assert project_image_loader(PID)(SlotItem(sku='sku', name='Name', price=100, image_url=path.as_uri())) is None


def test_real_preview_api_contains_uploaded_pixels_and_refreshes_changed_photos(project):
    import base64
    from fastapi.testclient import TestClient
    from store_emulator.application.storage.setups import new_setup_data, setup_path
    from store_emulator.domain.rack import Rack, Slot
    from store_emulator.domain.store import Store
    from store_emulator.domain.types import Face
    from store_emulator.server.main import app
    item = SlotItem(sku='uploaded', name='Visible product name', price=249)
    store = Store(id='s', name='Store', type='general', currency='USD', grid_size=(8, 8), racks=[
        Rack(id='rack', type='shelf', shape=[[1]], position=(2, 2), slots=[Slot(block=0, face=Face.S, level=3, items=[item])])])
    write_json(setup_path(PID, 'setup_chart'), new_setup_data('Chart', None, store.model_dump(mode='json')))
    client = TestClient(app)
    for color, pixel in [('red', (255, 0, 0)), ('blue', (0, 0, 255))]:
        uploaded = client.post(f'/api/projects/{PID}/sku-images', params={'sku': item.sku}, files={'file': ('photo.png', png(color), 'image/png')})
        assert uploaded.status_code == 200, uploaded.text
        response = client.post(f'/api/projects/{PID}/shelf-tests/preview', json={'setup_id': 'setup_chart', 'rack_id': 'rack', 'face': 'S'})
        assert response.status_code == 200, response.text
        image = Image.open(io.BytesIO(base64.b64decode(response.json()['control'].split(',', 1)[1]))).convert('RGB')
        assert sum(p == pixel for p in image.get_flattened_data()) > 100
