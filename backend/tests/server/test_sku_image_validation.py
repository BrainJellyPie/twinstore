"""Invalid replacement photos must not overwrite working SKU images."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path/'.data'/'proj_test'/'metadata.json',{'currency':'USD'})
    from store_emulator.server.main import app
    return TestClient(app,raise_server_exceptions=False)


def photo(fmt='PNG'):
    out=io.BytesIO()
    Image.new('RGB',(16,16),'white').save(out,format=fmt)
    return out.getvalue()


@pytest.mark.parametrize('limit,expected',[(100,413),(256,200)])
def test_sku_pixel_limit_is_reported_as_a_client_error(client,tmp_path,monkeypatch,limit,expected):
    data=photo()
    monkeypatch.setattr(Image,'MAX_IMAGE_PIXELS',limit)
    response=client.post('/api/projects/proj_test/sku-images/tea',files={'file':('tea.png',data,'image/png')})
    assert response.status_code==expected,response.text
    if expected==413:
        assert not (tmp_path/'.data'/'images').exists()


@pytest.mark.parametrize('fmt',['PNG','JPEG'])
def test_truncated_replacement_keeps_the_previous_photo_and_manifest(client,tmp_path,fmt):
    original=photo()
    saved=client.post('/api/projects/proj_test/sku-images/tea',files={'file':('tea.png',original,'image/png')})
    assert saved.status_code==200,saved.text
    root=tmp_path/'.data'/'images'/'proj_test'
    before={p.name:p.read_bytes() for p in root.iterdir()}
    full=photo(fmt)
    broken=full[:41] if fmt=='PNG' else full[:-2]
    response=client.post('/api/projects/proj_test/sku-images/tea',files={'file':('tea.'+fmt.lower(),broken,'image/'+fmt.lower())})
    assert response.status_code==422,response.text
    assert {p.name:p.read_bytes() for p in root.iterdir()}==before
    assert client.get(saved.json()['url']).content==original


@pytest.mark.parametrize('fmt',['JPEG','WEBP'])
def test_valid_images_preserve_original_encoded_bytes(client,fmt):
    data=photo(fmt)
    response=client.post('/api/projects/proj_test/sku-images/tea',files={'file':('tea.'+fmt.lower(),data,'image/'+fmt.lower())})
    assert response.status_code==200,response.text
    downloaded=client.get(response.json()['url'])
    assert downloaded.status_code==200
    assert downloaded.content==data


def test_oversized_replacement_preserves_existing_image(client,tmp_path):
    from store_emulator.application.storage.images import MAX_IMAGE_BYTES
    saved=client.post('/api/projects/proj_test/sku-images/tea',files={'file':('tea.png',photo(),'image/png')})
    assert saved.status_code==200,saved.text
    root=tmp_path/'.data'/'images'/'proj_test'
    before={p.name:p.read_bytes() for p in root.iterdir()}
    response=client.post('/api/projects/proj_test/sku-images/tea',files={'file':('large.png',b'x'*(MAX_IMAGE_BYTES+1),'image/png')})
    assert response.status_code==413,response.text
    assert {p.name:p.read_bytes() for p in root.iterdir()}==before
