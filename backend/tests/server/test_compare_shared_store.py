"""A run whose shoppers shared one store compared with one where each had it alone is not a layout comparison."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.types import Weekday


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"currency": "USD"})
    for run_id in ("run_a", "run_b"):
        customer = CustomerResult(persona_id="p1", day=Weekday.MON, arrival_time="12:00:00", total_spent=100)
        write_json(root / "runs" / run_id / "output" / "timeline.json", [customer.model_dump(mode="json")])
    from store_emulator.server.main import app
    return TestClient(app), root


def _notes(client: TestClient) -> list[str]:
    response = client.get("/api/projects/proj_test/compare?a=run_a&b=run_b&n_bootstrap=200")
    assert response.status_code == 200, response.text
    return response.json()["notes"]


def _config(root, run_id: str, operations: dict[str, object] | None) -> None:
    config: dict[str, object] = {"currency": "USD"}
    if operations is not None:
        config["operations"] = operations
    write_json(root / "runs" / run_id / "input" / "config.json", config)


def test_an_older_run_with_endless_stock_against_a_shared_store_says_so(runs):
    client, root = runs
    _config(root, "run_a", None)                           # 0.4.7: no operations in its config
    _config(root, "run_b", {"stock_per_facing": 12})
    assert any("In run_a each shopper had the store alone" in note for note in _notes(client))


def test_different_operations_are_noted_and_equal_ones_are_not(runs):
    client, root = runs
    _config(root, "run_a", {"stock_per_facing": 12})
    _config(root, "run_b", {"stock_per_facing": 4})
    assert any("different store operations" in note for note in _notes(client))
    _config(root, "run_b", {"stock_per_facing": 12})
    assert not any("store" in note and "operations" in note for note in _notes(client))


def test_notes_carry_their_kind_and_values_for_the_apps_language(runs):
    client, root = runs
    _config(root, "run_a", None)
    _config(root, "run_b", {"stock_per_facing": 12})
    report = client.get("/api/projects/proj_test/compare?a=run_a&b=run_b&n_bootstrap=200").json()
    assert len(report["note_codes"]) == len(report["notes"])
    assert {"code": "store_alone", "params": {"run": "run_a"}} in report["note_codes"]
    assert {"code": "few_paired", "params": {}} in report["note_codes"]


def test_two_runs_without_a_shared_store_need_no_note(runs):
    client, root = runs
    _config(root, "run_a", None)
    _config(root, "run_b", None)
    assert not any("alone" in note for note in _notes(client))
