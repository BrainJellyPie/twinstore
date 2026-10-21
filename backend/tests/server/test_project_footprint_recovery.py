"""A damaged optional layout thumbnail must not make the store gallery unavailable."""
import copy

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.projects import _footprint
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import read_state, setup_path


INVALID_STORES = [
    False, [], 'invalid store', {},
    {'grid_size': [None, 8]}, {'grid_size': ['wide', 6]}, {'grid_size': [0, 6]},
    {'grid_size': [-1, 6]}, {'grid_size': [True, 6]}, {'grid_size': [8.5, 6]},
    {'grid_size': [float('inf'), 6]}, {'grid_size': [10 ** 400, 6]},
    {'grid_size': [8, 6], 'racks': [None]},
    {'grid_size': [8, 6], 'racks': {'bad': 'rack'}},
    {'grid_size': [8, 6], 'racks': [{'type': 'shelf', 'shape': [1], 'position': [0, 0]}]},
    {'grid_size': [8, 6], 'racks': [{'type': 'shelf', 'shape': [[1]], 'position': ['bad', 0]}]},
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize('store', INVALID_STORES)
def test_gallery_still_lists_projects_when_the_active_store_cannot_be_drawn(client, store):
    before = client.get('/api/projects')
    assert before.status_code == 200
    pid = 'proj_67916afd'
    path = setup_path(pid, read_state(pid)['activeSetupId'])
    setup = read_json(path)
    setup['store'] = copy.deepcopy(store)
    write_json(path, setup)
    response = client.get('/api/projects')
    assert response.status_code == 200, response.text
    assert {p['project_id'] for p in response.json()} == {p['project_id'] for p in before.json()}
    item = next(p for p in response.json() if p['project_id'] == pid)
    footprint = item.get('footprint')
    assert footprint is None or (footprint['grid'] == [8, 6] and footprint['racks'] == [])


@pytest.mark.parametrize('broken', [None, [], 'bad', {'type': 'shelf', 'shape': [1]},
    {'type': 'shelf', 'shape': [[1]], 'position': ['bad', 0]},
    {'type': 'shelf', 'shape': [[1]], 'position': [float('inf'), 0]},
])
def test_one_bad_fixture_does_not_hide_the_remaining_valid_fixture(broken):
    good = {'type': 'fridge', 'shape': [[1, 1]], 'position': [2, 3], 'rotation': 90}
    store = {'grid_size': [8, 6], 'racks': [broken, good]}
    assert _footprint(store) == {'grid': [8, 6], 'racks': [[2, 3, 1, 2, 'fridge']]}
