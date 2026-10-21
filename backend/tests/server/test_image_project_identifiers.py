"""SKU images accept the API's safe project IDs while rejecting paths."""
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from store_emulator.application.storage import images
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data
from store_emulator.engine.layout_gen import generate_store


@pytest.mark.parametrize('pid',['Project-A','proj_UPPER','project-with-hyphen','proj_lower'])
def test_image_and_layout_routes_accept_safe_project_ids(tmp_path,monkeypatch,pid):
    monkeypatch.chdir(tmp_path)
    root=tmp_path/'.data'/pid
    write_json(root/'metadata.json',{'currency':'USD','name':'Test'})
    source=new_setup_data('Source',None,generate_store('mini_mart').model_dump(mode='json'))
    source['id']='setup_test'
    write_json(root/'setups'/'setup_test.json',source)
    from store_emulator.server.main import app
    client=TestClient(app,raise_server_exceptions=False)
    response=client.get(f'/api/projects/{pid}/setups/setup_test')
    assert response.status_code==200,response.text
    data=io.BytesIO()
    Image.new('RGB',(8,8),'white').save(data,format='PNG')
    uploaded=client.post(f'/api/projects/{pid}/sku-images/tea',files={'file':('tea.png',data.getvalue(),'image/png')})
    assert uploaded.status_code==200,uploaded.text
    fetched=client.get(uploaded.json()['url'])
    assert fetched.status_code==200
    assert fetched.content==data.getvalue()


@pytest.mark.parametrize('pid',['../outside','/tmp/outside','..\\outside','project/name','project.name',''])
def test_image_storage_still_rejects_project_paths(tmp_path,monkeypatch,pid):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError,match='unsafe project_id'):
        images.load_manifest(pid)
    assert not (tmp_path/'.data').exists()
