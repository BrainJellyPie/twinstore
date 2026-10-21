"""A stop request must prevent further optimization work and result publication."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import optimize
from store_emulator.application.storage.io import write_json
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import SimulationSummary
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator


@pytest.mark.parametrize('algorithm', ['hill_climb', 'anneal', 'genetic'])
@pytest.mark.parametrize('phase', ['pending', 'baseline', 'candidate', 'last_candidate', 'validation', 'final_validation', 'never'])
def test_rule_optimization_respects_stop_requests(tmp_path, monkeypatch, algorithm, phase):
    monkeypatch.chdir(tmp_path)
    pid, sid = 'proj_test', 'setup_test'
    folder = tmp_path / '.data' / pid
    write_json(folder / 'metadata.json', {'currency':'USD'})
    write_json(folder / 'setups' / f'{sid}.json', {'id':sid,'name':'Original','store':generate_store('mini_mart').model_dump(mode='json')})
    persona = Persona(id='p0',identity='Shopper',age_group='20s',gender='Female',description='Tea',intent='tea',purpose='tea')
    write_json(folder / 'personas.json',[persona.model_dump(mode='json')])
    executor=Mock()
    monkeypatch.setattr(optimize,'executor',executor)
    search_calls=0
    validation_calls=0
    job=''

    async def evaluate(self, store):
        nonlocal search_calls
        search_calls += 1
        if (phase=='baseline' and search_calls==1) or (phase in ('candidate', 'last_candidate') and search_calls==2):
            optimize.cancel_optimization(pid,job)
        score=100 if search_calls==1 else 200
        return score,SimulationSummary(store_id=store.id,revenue_per_visitor=score)

    async def evaluate_customers(self, store, personas, *, replicate=None):
        nonlocal validation_calls
        validation_calls += 1
        if (phase=='validation' and validation_calls==1) or (phase=='final_validation' and validation_calls==2):
            optimize.cancel_optimization(pid,job)
        return []

    monkeypatch.setattr(LayoutEvaluator,'evaluate',evaluate)
    monkeypatch.setattr(LayoutEvaluator,'evaluate_customers',evaluate_customers)
    from store_emulator.server.main import app
    client=TestClient(app)
    response=client.post(f'/api/projects/{pid}/setups/{sid}/optimize',json={'spec':{
        'algorithm':algorithm,'budget':1 if phase=='last_candidate' else 6,'eval_customers':20,'validation_customers':20}})
    assert response.status_code == 200,response.text
    job=response.json()['job_id']
    if phase=='pending':
        assert client.post(f'/api/projects/{pid}/optimizations/{job}/cancel').status_code==200
    args=executor.submit.call_args.args
    args[0](*args[1:])
    view=client.get(f'/api/projects/{pid}/optimizations/{job}').json()
    assert (pid, job) not in optimize._cancel_requests
    if phase=='never':
        assert view['status']['status']=='completed',view
        assert view['result'] is not None
        assert search_calls==7 and validation_calls==2
        return
    assert view['status']['status']=='canceled',view
    assert view['result'] is None
    if phase=='pending':
        assert search_calls==validation_calls==0
    elif phase=='baseline':
        assert search_calls==1 and validation_calls==0
    elif phase in ('candidate', 'last_candidate'):
        assert search_calls==2 and validation_calls==0
    else:
        assert validation_calls==(1 if phase=='validation' else 2)
