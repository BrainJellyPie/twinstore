"""A deleted source layout is a missing resource, not an internal server error."""
import pytest
from fastapi.testclient import TestClient
from store_emulator.application.optimize import OptimizationStatus
from store_emulator.application.storage.io import write_json
from store_emulator.domain.optimize import OptimizeResult, OptimizeSpec
from store_emulator.engine.layout_gen import generate_store


@pytest.mark.parametrize('custom_name',[None,'Saved result'])
def test_deleted_source_returns_not_found_without_creating_a_layout(tmp_path,monkeypatch,custom_name):
    monkeypatch.chdir(tmp_path)
    pid,job='proj_test','opt_test'
    root=tmp_path / '.data' / pid
    folder=root / 'optimizations' / job
    spec=OptimizeSpec(budget=1,eval_customers=10)
    status=OptimizationStatus(job_id=job,setup_id='setup_deleted',status='completed',spec=spec)
    result=OptimizeResult(spec=spec,baseline_score=100,best_score=110,relative_improvement=.1,
        best_store=generate_store('mini_mart'),applied_moves=['Move tea'],history=[],evaluations=1,seconds=0)
    write_json(root / 'metadata.json',{'currency':'USD'})
    write_json(folder/'status.json',status.model_dump(mode='json'))
    write_json(folder/'result.json',result.model_dump(mode='json'))
    before={p.relative_to(root):p.read_bytes() for p in root.rglob('*.json')}
    from store_emulator.server.main import app
    response=TestClient(app,raise_server_exceptions=False).post(f'/api/projects/{pid}/optimizations/{job}/apply',json={'name':custom_name})
    assert response.status_code==404,response.text
    assert 'source' in response.json()['detail'].lower()
    assert {p.relative_to(root):p.read_bytes() for p in root.rglob('*.json')}==before
    assert not (root/'setups').exists()
