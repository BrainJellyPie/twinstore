"""Study registration cannot race project deletion or read an unfinished input save."""

import io
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock
from PIL import Image

from store_emulator.application import marketing, projects, setups, staff_pitch
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup
from store_emulator.domain.config import LLMConfig
from store_emulator.server.main import app
from tests.server.test_experiment_start_snapshot import _overlap
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture(params=["survey", "shelf", "conjoint", "pitch"])
def study(layout, monkeypatch, request):
    kind = request.param
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    monkeypatch.setattr(marketing, "capture_llm_config", Mock(return_value=LLMConfig(model="fake")))
    monkeypatch.setattr(marketing, "LiteLLMClient", Mock())
    monkeypatch.setattr(staff_pitch, "build_client", Mock())
    seen = []

    async def panel(_llm, people, *args, **kwargs):
        seen.append(([p.id for p in people], args))
        # Stop before model work or estimation; existing API tests exercise complete reports.
        raise ValueError("test panel reached")

    monkeypatch.setattr(marketing, "survey_panel", panel)
    monkeypatch.setattr(marketing, "shelf_panel", panel)
    monkeypatch.setattr(marketing, "conjoint_panel", panel)
    monkeypatch.setattr(staff_pitch, "test_pitch_panel", panel)
    original = read_json(personas_path(PID))[0]
    write_json(personas_path(PID), [{**original, "id": f"p{i}"} for i in range(20)])
    store = read_setup(PID, SID)["store"]
    rack, sku = next((r, item["sku"]) for r in store["racks"] for slot in r["slots"] for item in slot["items"])
    client = TestClient(app)
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(data, format="PNG")
    uploaded = client.post(f"/api/projects/{PID}/lab/packages", files={"image": ("pack.png", data.getvalue(), "image/png")})
    assert uploaded.status_code == 200, uploaded.text
    endpoint, body = {
        "survey": ("surveys", {"stimuli": [uploaded.json()["asset_id"]], "questions": ["appeal"]}),
        "shelf": ("shelf-tests", {"setup_id": SID, "rack_id": rack["id"], "target_sku": sku,
                                  "changes": [{"kind": "promo", "sku": sku, "promo": "NEW"}]}),
        "conjoint": ("conjoints", {"product": "Tea", "prices": [100, 200],
                                    "attributes": [{"name": "Flavor", "levels": ["Peach", "Lemon"]}]}),
        "pitch": ("staff-pitches", {"setup_id": SID, "sku": sku, "context": "Browsing a shelf.", "variants": [
            {"name": "A", "script": "Try this tea."}, {"name": "B", "script": "Enjoy a fresh tea."},
        ]}),
    }[kind]
    return kind, client, f"/api/projects/{PID}/{endpoint}", {**body, "panel": 20}, submit, seen


@pytest.mark.parametrize("start_first", [False, True])
def test_study_registration_excludes_project_deletion(study, monkeypatch, start_first):
    kind, client, url, body, submit, _ = study
    start = lambda: client.post(url, json=body)
    delete = lambda: client.delete(f"/api/projects/{PID}")
    if start_first:
        started, deleted = _overlap(monkeypatch, marketing, "_write_status", start, delete)
    else:
        deleted, started = _overlap(monkeypatch, projects, "remove_tree", delete, start)
    assert started.status_code == (200 if start_first else 404), started.text
    assert deleted.status_code == (409 if start_first else 200), deleted.text
    assert submit.call_count == (1 if start_first else 0)
    assert metadata_path(PID).parent.exists() is start_first
    assert len(marketing.list_jobs(PID, kind)) == (1 if start_first else 0)


def test_accepted_customer_save_supplies_the_study_panel(study, monkeypatch):
    _, client, url, body, submit, seen = study
    people = [{**p, "id": f"edited_{p['id']}"} for p in read_json(personas_path(PID))]
    _, started = _overlap(monkeypatch, projects, "write_json",
                         lambda: projects.save_project_personas(PID, people), lambda: client.post(url, json=body))
    assert started.status_code == 200, started.text
    submit.call_args.args[0]()
    assert client.get(f"{url}/{started.json()['job_id']}").json()["status"] == "failed"
    assert len(seen) == 1
    assert set(seen[0][0]) == {p["id"] for p in people}


def test_later_customer_save_does_not_change_a_registered_panel(study):
    _, client, url, body, submit, seen = study
    before = read_json(personas_path(PID))
    started = client.post(url, json=body)
    assert started.status_code == 200, started.text
    projects.save_project_personas(PID, [{**p, "id": f"later_{p['id']}"} for p in before])
    submit.call_args.args[0]()
    assert len(seen) == 1
    assert set(seen[0][0]) == {p["id"] for p in before}


@pytest.mark.parametrize("locked", ["tree", SID, "unrelated"])
def test_busy_study_inputs_register_nothing_until_available(study, monkeypatch, locked):
    kind, client, url, body, submit, _ = study
    factory = lambda path, timeout: FileLock(path, timeout=0)
    for module in (setups, marketing, staff_pitch):
        monkeypatch.setattr(module, "FileLock", factory, raising=False)
    path = setups.setup_lock_path(PID, locked)
    if locked == "tree":
        path = path.with_name(".setup-tree.lock")
    with FileLock(path, timeout=0):
        started = client.post(url, json=body)
    blocked = locked == "tree" or (locked == SID and kind in {"shelf", "pitch"})
    assert started.status_code == (503 if blocked else 200), started.text
    assert submit.call_count == (0 if blocked else 1)
    assert len(marketing.list_jobs(PID, kind)) == (0 if blocked else 1)


@pytest.mark.parametrize("study", ["shelf", "pitch"], indirect=True)
def test_accepted_product_edit_supplies_layout_studies(study, monkeypatch):
    kind, client, url, body, submit, seen = study
    store = read_setup(PID, SID)["store"]
    for rack in store["racks"]:
        for slot in rack["slots"]:
            for item in slot["items"]:
                item["name"] = "Edited product"
    _, started = _overlap(monkeypatch, setups, "write_setup",
                         lambda: setups.save_setup_with_lock(PID, SID, {"store": store}),
                         lambda: client.post(url, json=body))
    assert started.status_code == 200, started.text
    submit.call_args.args[0]()
    assert len(seen) == 1
    args = seen[0][1]
    if kind == "shelf":
        assert {item.name for rack in args[:2] for slot in rack.slots for item in slot.items} == {"Edited product"}
    else:
        assert args[1].name == "Edited product"


def test_waiting_study_start_leaves_the_server_responsive(study, monkeypatch):
    kind, _, url, body, submit, _ = study

    @asynccontextmanager
    async def no_startup(_app):
        yield

    monkeypatch.setattr(app.router, "lifespan_context", no_startup)
    path = setups.setup_lock_path(PID, SID)
    module = staff_pitch if kind == "pitch" else marketing
    if kind in {"survey", "conjoint"}:
        path = path.with_name(".setup-tree.lock")
        module = setups
    attempted = Event()

    def observed_lock(lock_path, timeout):
        if Path(lock_path) == path:
            attempted.set()
        return FileLock(lock_path, timeout=timeout)

    monkeypatch.setattr(module, "FileLock", observed_lock)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        with FileLock(path, timeout=0):
            pending = pool.submit(client.post, url, json=body)
            assert attempted.wait(5)
            assert pool.submit(client.get, "/api/health").result(timeout=1).json() == {"status": "ok"}
            assert not pending.done()
        assert pending.result(timeout=5).status_code == 200
    submit.assert_called_once()
