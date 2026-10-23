"""Late POS/movement reports cannot recreate projects deleted during analysis."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import movement, projects, setups, simulation
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, read_setup
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.types import Action, Weekday
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID, SID, layout

RUN = "run_analysis"


@pytest.fixture
def analysis(layout):
    store = read_setup(PID, SID)["store"]
    sku = next(item["sku"] for rack in store["racks"] for slot in rack["slots"] for item in slot["items"])
    base = metadata_path(PID).parent / "runs" / RUN
    write_json(base / "input" / "store.json", store)
    customer = CustomerResult(persona_id="p", day=Weekday.MON, arrival_time="10:00:00", timeline=[
        TimelineEvent(elapsed_sec=0, x=0, y=0, action=Action.ENTER),
        TimelineEvent(elapsed_sec=10, x=0, y=0, action=Action.EXIT),
    ])
    write_json(base / "output" / "timeline.json", [customer.model_dump(mode="json")])
    data = {"fidelity": f"receipt_id,sku,quantity\nr1,{sku},1\n".encode(),
            "movement": b"track_id,x,y,timestamp_sec\nt1,0,0,0\nt1,0,0,10\n"}
    return TestClient(app), base, data


def score(client, data, operation):
    return client.post(f"/api/projects/{PID}/runs/{RUN}/{operation}",
                       files={"file": ("observations.csv", data[operation], "text/csv")})


@pytest.mark.parametrize("operation", ["fidelity", "movement"])
@pytest.mark.parametrize("phase", ["calculation", "write", "delete_first"])
def test_analysis_and_deletion_do_not_recreate_outputs(analysis, monkeypatch, operation, phase):
    client, base, data = analysis
    save = lambda: score(client, data, operation)
    delete = lambda: client.delete(f"/api/projects/{PID}")
    if phase == "delete_first":
        deleted, scored = overlap(monkeypatch, projects, "remove_tree", delete, save)
    elif phase == "calculation":
        module, method = (simulation, "fidelity_report") if operation == "fidelity" else (movement, "movement_report")
        scored, deleted = overlap(monkeypatch, module, method, save, delete)
    else:
        writer = SimpleNamespace(write=write_json)
        forward = lambda *a, **kw: writer.write(*a, **kw)
        monkeypatch.setattr(simulation, "write_json", forward)
        monkeypatch.setattr(movement, "write_json", forward, raising=False)
        scored, deleted = overlap(monkeypatch, writer, "write", save, delete)
    assert deleted.status_code == 200, deleted.text
    assert scored.status_code == (200 if phase == "write" else 404), scored.text
    assert not metadata_path(PID).parent.exists()
    assert not base.exists()


@pytest.mark.parametrize("operation", ["fidelity", "movement"])
def test_busy_project_preserves_existing_analysis_report(analysis, monkeypatch, operation):
    client, base, data = analysis
    assert score(client, data, operation).status_code == 200
    path = base / "output" / f"{operation}.json"
    before = path.read_bytes()
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    lock = setups.setup_lock_path(PID, "tree").with_name(".setup-tree.lock")
    with FileLock(lock, timeout=0):
        response = score(client, data, operation)
    assert response.status_code == 503, response.text
    assert path.read_bytes() == before
