"""Invalid persona payloads must not replace a project's usable respondent data."""

import json

import pytest
from fastapi.testclient import TestClient

from store_emulator.domain.persona import Persona


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    root.mkdir(parents=True)
    persona = Persona(id="p_test", identity="Student", age_group="20s", gender="Female",
                      description="Buys a snack after class", intent="snack", purpose="snack")
    (root / "personas.json").write_text(json.dumps([persona.model_dump(mode="json")]))
    (root / "metadata.json").write_text(json.dumps({"name": "Test", "updated_at": "original"}))
    from store_emulator.server.main import app
    return TestClient(app), root, persona


@pytest.mark.parametrize("invalid", [None, "not a persona", {}, {"id": "p_invalid", "age_group": "unknown"}])
def test_invalid_persona_does_not_overwrite_existing_data(project, invalid):
    client, root, persona = project
    previous = (root / "personas.json").read_bytes()
    response = client.put("/api/projects/proj_test/personas", json={
        "personas": [persona.model_dump(mode="json"), invalid],
    })
    assert response.status_code == 422
    assert (root / "personas.json").read_bytes() == previous
    assert json.loads((root / "metadata.json").read_text())["updated_at"] == "original"


def test_valid_personas_are_saved_in_a_reloadable_format(project):
    client, root, persona = project
    updated = persona.model_copy(update={"identity": "Graduate student"})
    response = client.put("/api/projects/proj_test/personas", json={"personas": [updated.model_dump(mode="json")]})
    assert response.status_code == 200
    saved = json.loads((root / "personas.json").read_text())
    assert [Persona.model_validate(p) for p in saved] == [updated]


def test_personas_with_simulation_history_remain_locked(project):
    client, root, persona = project
    setups = root / "setups"
    setups.mkdir()
    (setups / "setup_test.json").write_text(json.dumps({"id": "setup_test", "runId": "run_test"}))
    previous = (root / "personas.json").read_bytes()
    response = client.put("/api/projects/proj_test/personas", json={"personas": [persona.model_dump(mode="json")]})
    assert response.status_code == 409
    assert (root / "personas.json").read_bytes() == previous


@pytest.mark.parametrize("rate", [-0.01, 1.01, "NaN", "Infinity", "-Infinity"])
def test_invalid_purchase_frequencies_preserve_saved_personas(project, rate):
    client, root, persona = project
    previous = (root / "personas.json").read_bytes()
    data = {**persona.model_dump(mode="json"), "category_rates": {"drinks": rate}}
    response = client.put("/api/projects/proj_test/personas", json={"personas": [data]})
    assert response.status_code == 422, response.text
    assert (root / "personas.json").read_bytes() == previous
    assert json.loads((root / "metadata.json").read_text())["updated_at"] == "original"


@pytest.mark.parametrize("field", ["budget_min", "budget_max"])
def test_negative_budgets_preserve_saved_personas(project, field):
    client, root, persona = project
    previous = (root / "personas.json").read_bytes()
    data = {**persona.model_dump(mode="json"), field: -1}
    response = client.put("/api/projects/proj_test/personas", json={"personas": [data]})
    assert response.status_code == 422, response.text
    assert (root / "personas.json").read_bytes() == previous
    assert json.loads((root / "metadata.json").read_text())["updated_at"] == "original"


@pytest.mark.parametrize("rate", [0, 1])
def test_frequency_boundaries_remain_readable(project, rate):
    client, _, persona = project
    data = {**persona.model_dump(mode="json"), "category_rates": {"drinks": rate}}
    response = client.put("/api/projects/proj_test/personas", json={"personas": [data]})
    assert response.status_code == 200, response.text
    saved = client.get("/api/projects/proj_test").json()["personas"][0]
    assert saved["category_rates"] == {"drinks": rate}
    assert saved["budget_min"] == saved["budget_max"] == 0


@pytest.mark.parametrize("hour", [-100, -1, 24, 25, 100, "-1", "24"])
def test_invalid_arrival_hours_cannot_silently_remove_saved_customers(project, hour):
    client, root, persona = project
    previous = (root / "personas.json").read_bytes()
    data = {**persona.model_dump(mode="json"), "arrival_hour": hour}
    response = client.put("/api/projects/proj_test/personas", json={"personas": [data]})
    assert response.status_code == 422, response.text
    assert (root / "personas.json").read_bytes() == previous
    assert json.loads((root / "metadata.json").read_text())["updated_at"] == "original"


@pytest.mark.parametrize("hour", [0, 1, 22, 23, "0", "23"])
def test_boundary_arrival_hours_survive_save_and_simulation_admission(project, hour):
    from store_emulator.domain.store import DaySchedule
    from store_emulator.engine.layout_gen import generate_store
    from tests.engine.test_simulation_opening_hours import _runner

    client, root, persona = project
    data = {**persona.model_dump(mode="json"), "arrival_hour": hour}
    response = client.put("/api/projects/proj_test/personas", json={"personas": [data]})
    assert response.status_code == 200, response.text
    saved = [Persona.model_validate(p) for p in json.loads((root / "personas.json").read_text())]
    store = generate_store("station_kiosk")
    store.weekly_schedule = [DaySchedule(day=1, open_hour=0, close_hour=24)]
    runner, _ = _runner()
    _, entries, _ = runner._validate_and_prepare(store, saved, path_heatmap=False)
    assert len(entries) == 1
    assert entries[0][0].hour == int(hour)
    assert entries[0][0].arrival_time.startswith(f"{int(hour):02d}:")
