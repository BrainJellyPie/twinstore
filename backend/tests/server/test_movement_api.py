import json

import pytest
from fastapi.testclient import TestClient

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action

PID = "proj_67916afd"
RUN = "movement_test"
URL = f"/api/projects/{PID}/runs/{RUN}/movement"
CSV = b"track_id,x,y,timestamp_sec\nprivate_track_4a,0,0,0\nprivate_track_4a,1,0,5\nprivate_track_4a,1,1,15\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".data" / PID / "runs" / RUN
    (base / "input").mkdir(parents=True)
    (base / "output").mkdir()
    (base / "input" / "store.json").write_text(Store(id="s", name="s", type="test", grid_size=(2, 2)).model_dump_json())
    customer = CustomerResult(persona_id="p", day=1, arrival_time="09:00:00", timeline=[
        TimelineEvent(elapsed_sec=t, x=x, y=y, action=Action.MOVE) for t, x, y in [(0, 0, 0), (5, 1, 0), (15, 1, 1)]
    ])
    (base / "output" / "timeline.json").write_text(json.dumps([customer.model_dump()]))
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_compare_and_retrieve_only_aggregates(client, tmp_path):
    assert client.get(URL).json() is None
    response = client.post(URL, files={"file": ("tracks.csv", CSV, "text/csv")})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["visitation_similarity"] == report["occupancy_similarity"] == 1
    assert report["observed"]["occupancy_seconds"] == [[5, 10], [0, 0]]
    assert client.get(URL).json() == report
    path = tmp_path / ".data" / PID / "runs" / RUN / "output" / "movement.json"
    assert "private_track_4a" not in path.read_text()
    assert not list(tmp_path.rglob("tracks.csv"))


def test_bad_upload_preserves_previous_report(client):
    original = client.post(URL, files={"file": ("tracks.csv", CSV, "text/csv")}).json()
    for content in [b"track_id,x,y,timestamp_sec\na,99,0,1\n", b"track_id,x,y,timestamp_sec\n", b"wrong header\n"]:
        response = client.post(URL, files={"file": ("bad.csv", content, "text/csv")})
        assert response.status_code == 400, response.text
    assert client.get(URL).json() == original
    assert client.post(URL, files={"file": ("tracks.csv", CSV)}, data={"max_gap_seconds": "nan"}).status_code == 422
    assert client.get(f"/api/projects/{PID}/runs/missing/movement").status_code == 404


def test_missing_intervals_are_reported(client):
    response = client.post(URL, files={"file": ("tracks.csv", CSV)}, data={"max_gap_seconds": "6"})
    assert response.status_code == 200
    assert response.json()["observed"]["excluded_seconds"] == 10
    assert response.json()["simulated"]["excluded_seconds"] == 0
