"""An ID longer than a file name can be is refused as invalid, not answered with a server error."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"
LONG = "a" * 300


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.parametrize("path", [
    f"/api/projects/{PID}/runs/{LONG}/status",
    f"/api/projects/{PID}/setups/{LONG}",
    f"/api/projects/{PID}/captures/{LONG}",
    f"/api/projects/{PID}/experiments/{LONG}",
    f"/api/projects/{PID}/online/sites/{LONG}",
    f"/api/projects/{PID}/online/runs/{LONG}",
    f"/api/projects/{LONG}",
])
def test_an_overlong_id_is_invalid_not_a_server_error(client, path):
    response = client.get(path)
    assert response.status_code == 400, response.text


def test_a_run_cannot_be_started_under_an_overlong_id(client):
    setups = client.get(f"/api/projects/{PID}/setups").json()
    response = client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": setups[0]["id"], "run_id": LONG, "engine_type": "rule_based", "preview": True,
    })
    assert response.status_code == 422, response.text


def test_an_id_of_128_characters_is_still_a_valid_name(client):
    assert client.get(f"/api/projects/{PID}/runs/{'b' * 128}/status").status_code == 404


@pytest.mark.parametrize("length", [129, 255, 256])
def test_id_limit_applies_before_filesystem_component_limits(client, length):
    assert client.get(f"/api/projects/{PID}/runs/{'b' * length}/status").status_code == 400
