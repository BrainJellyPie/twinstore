"""An A/B study keeps one committed input snapshot, including its traffic scale."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import marketing, projects, setups
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.operations import OperationsConfig
from store_emulator.engine.optimize.evaluate import LayoutEvaluator
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def study(layout, monkeypatch):
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    seen = []

    async def evaluate(self, store, people):
        seen.append((store.name, [p.id for p in people], self.config.operations))
        return [CustomerResult(persona_id=p.id, day=p.day, arrival_time="12:00:00") for p in people]

    monkeypatch.setattr(LayoutEvaluator, "evaluate_customers", evaluate)
    store = read_setup(PID, SID)["store"]
    sku = next(item["sku"] for rack in store["racks"] for slot in rack["slots"] for item in slot["items"])
    body = {"setup_id": SID, "panel": 20, "focus_skus": [sku],
            "variants": [{"name": "Sign", "changes": [{"kind": "promo", "sku": sku, "promo": "NEW"}]}]}
    return TestClient(app), submit, seen, body


def _overlap(monkeypatch, module, method, first, second):
    ready, release = Event(), Event()
    original = getattr(module, method)

    def paused(*args, **kwargs):
        ready.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, method, paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        try:
            assert ready.wait(5)
            b = pool.submit(second)
            try:
                b.result(timeout=0.2)
            except TimeoutError:
                pass
        finally:
            release.set()
        return a.result(timeout=5), b.result(timeout=5)


@pytest.mark.parametrize("start_first", [False, True])
def test_study_registration_and_project_deletion_are_exclusive(study, monkeypatch, start_first):
    client, submit, _, body = study

    def start():
        return client.post(f"/api/projects/{PID}/experiments", json=body)

    def delete():
        return client.delete(f"/api/projects/{PID}")

    if start_first:
        started, deleted = _overlap(monkeypatch, marketing, "_write_status", start, delete)
    else:
        deleted, started = _overlap(monkeypatch, projects, "remove_tree", delete, start)
    assert started.status_code == (200 if start_first else 404), started.text
    assert deleted.status_code == (409 if start_first else 200), deleted.text
    assert submit.call_count == (1 if start_first else 0)
    assert metadata_path(PID).parent.exists() is start_first
    assert len(marketing.list_jobs(PID, "experiment")) == (1 if start_first else 0)


@pytest.mark.parametrize("kind", ["layout", "customers", "operations", "clear_operations"])
def test_study_uses_accepted_input_edits(study, monkeypatch, kind):
    client, submit, seen, body = study
    setups.save_layout_operations(PID, SID, OperationsConfig(stock_per_facing=5))
    store = {**read_setup(PID, SID)["store"], "name": "Edited store"}
    people = [{**read_json(personas_path(PID))[0], "id": "edited_customer"}]
    operations = None if kind == "clear_operations" else OperationsConfig(stock_per_facing=33)

    def edit():
        if kind == "layout":
            return setups.save_setup_with_lock(PID, SID, {"store": store})
        if kind == "customers":
            return projects.save_project_personas(PID, people)
        return setups.save_layout_operations(PID, SID, operations)

    _, started = _overlap(monkeypatch, projects if kind == "customers" else setups,
        "write_json" if kind == "customers" else "write_setup", edit,
        lambda: client.post(f"/api/projects/{PID}/experiments", json=body),
    )
    assert started.status_code == 200, started.text
    submit.assert_called_once()
    submit.call_args.args[0]()
    view = marketing.get_experiment(PID, started.json()["job_id"])
    assert view.status == "completed", view.error
    assert len(seen) == 2  # control and variant both use the captured population and settings
    for name, ids, config in seen:
        if kind == "layout":
            assert name == "Edited store"
        elif kind == "customers":
            assert ids == ["edited_customer"]
        else:
            assert config == operations


@pytest.mark.parametrize("later_estimate", [None, 900])
def test_experiment_keeps_the_traffic_scale_that_belongs_to_its_captured_people(study, later_estimate):
    client, submit, _, body = study
    meta = read_json(metadata_path(PID))
    write_json(metadata_path(PID), {**meta, "estimated_daily_visitors": {"1": 100}})
    started = client.post(f"/api/projects/{PID}/experiments", json=body)
    assert started.status_code == 200, started.text
    later = meta if later_estimate is None else {**meta, "estimated_daily_visitors": {"1": later_estimate}}
    write_json(metadata_path(PID), later)
    submit.call_args.args[0]()
    view = marketing.get_experiment(PID, started.json()["job_id"])
    assert view.status == "completed", view.error
    assert view.report.visitors_per_day == 100
    assert view.report.simulated_visitors_per_day == 1
    assert read_json(metadata_path(PID)) == later


@pytest.mark.parametrize("locked", ["tree", SID, "unrelated"])
def test_busy_study_inputs_return_retryable_error_without_a_job(study, monkeypatch, locked):
    client, submit, _, body = study
    factory = lambda path, timeout: FileLock(path, timeout=0)
    monkeypatch.setattr(setups, "FileLock", factory)
    monkeypatch.setattr(marketing, "FileLock", factory, raising=False)
    path = setups.setup_lock_path(PID, locked)
    if locked == "tree":
        path = path.with_name(".setup-tree.lock")
    with FileLock(path, timeout=0):
        response = client.post(f"/api/projects/{PID}/experiments", json=body)
    expected = 200 if locked == "unrelated" else 503
    assert response.status_code == expected, response.text
    assert submit.call_count == (1 if expected == 200 else 0)
    assert len(marketing.list_jobs(PID, "experiment")) == (1 if expected == 200 else 0)
