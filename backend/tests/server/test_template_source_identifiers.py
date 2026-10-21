"""Template reuse accepts the same safe layout IDs as the rest of the API."""
import pytest
from fastapi.testclient import TestClient
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data
from store_emulator.engine.layout_gen import generate_store


@pytest.mark.parametrize('source_id',['Layout-A','setup_UPPER','layout-with-hyphen','setup_lower'])
@pytest.mark.parametrize('building',[False,True])
def test_template_reuse_preserves_valid_source_ids(tmp_path,monkeypatch,source_id,building):
    monkeypatch.chdir(tmp_path)
    pid='proj_test'
    root=tmp_path/'.data'/pid
    write_json(root/'metadata.json',{'currency':'USD','name':'Test'})
    source=new_setup_data('Source',None,generate_store('mini_mart').model_dump(mode='json'))
    source['id']=source_id
    path=root/'setups'/f'{source_id}.json'
    write_json(path,source)
    before=path.read_bytes()
    from store_emulator.server.main import app
    client=TestClient(app)
    assert client.get(f'/api/projects/{pid}/setups/{source_id}').status_code==200
    layout={'template_id':'mini_mart','source_setup_id':source_id}
    if building:
        response=client.post(f'/api/projects/{pid}/setups/generate-building',json={'name':'New building','floors':[
            {'label':label,'layout':layout} for label in ['Ground','Upper']]})
    else:
        response=client.post(f'/api/projects/{pid}/setups/generate',json=layout)
    assert response.status_code==200,response.text
    saved=response.json()['setups'] if building else [response.json()]
    assert all(s['parentId']==source_id for s in saved)
    assert path.read_bytes()==before
