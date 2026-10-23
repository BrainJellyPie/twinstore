"""Invalid saved populations cannot launch paid work or collapse customer identities."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import optimize, run_estimate, shelf_lab, simulation
from store_emulator.application.async_executor import executor
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import personas_path, read_setup
from store_emulator.domain.persona import Persona
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


INVALID = ["duplicate", "blank", "whitespace", "null_record", "missing_field", "bad_hour",
           "null", "number", "string", "object", "broken_json"]


def _damage(kind):
    person = read_json(personas_path(PID))[0]
    values = {
        "duplicate": [person, {**person, "identity": "Different shopper"}],
        "blank": [{**person, "id": ""}],
        "whitespace": [{**person, "id": " \t\n"}],
        "null_record": [person, None],
        "missing_field": [{k: v for k, v in person.items() if k != "age_group"}],
        "bad_hour": [{**person, "arrival_hour": 24}],
        "null": None, "number": 123, "string": "customers", "object": {person["id"]: person},
    }
    if kind == "broken_json":
        personas_path(PID).write_text('[{"id":')
    else:
        write_json(personas_path(PID), values[kind])
    return personas_path(PID).read_bytes()


@pytest.mark.parametrize("kind", INVALID)
@pytest.mark.parametrize("endpoint", ["runs", "runs/estimate", "optimize"])
def test_invalid_population_is_rejected_before_jobs_and_model_work(layout, monkeypatch, kind, endpoint):
    before = _damage(kind)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    client = TestClient(app, raise_server_exceptions=False)
    if endpoint == "optimize":
        url = f"/api/projects/{PID}/setups/{SID}/optimize"
        body = {"spec": {"budget": 2, "eval_customers": 10}}
    else:
        url = f"/api/projects/{PID}/{endpoint}"
        body = {"setup_id": SID, "run_id": "run_invalid", "engine_type": "rule_based", "max_customers": 1}
    response = client.post(url, json=body)
    # Readiness can already reject an absent/wrong-shaped customer list for run starts.
    if endpoint == "runs" and kind in {"null", "number", "string", "object", "broken_json"}:
        assert response.status_code == 409, response.text
    else:
        assert response.status_code == 400, response.text
        assert "personas.json" in response.json()["detail"]
    submit.assert_not_called()
    assert read_setup(PID, SID)["status"] == "draft"
    assert not (Path(".data") / PID / "runs").exists()
    assert not (Path(".data") / PID / "optimizations").exists()
    assert personas_path(PID).read_bytes() == before


@pytest.mark.parametrize("kind", INVALID)
def test_marketing_and_shelf_studies_reject_the_same_invalid_customers(layout, kind):
    before = _damage(kind)
    with pytest.raises(AppError, match="personas.json"):
        shelf_lab._personas(PID)
    assert personas_path(PID).read_bytes() == before


@pytest.mark.parametrize("identifiers", [["01", "1"], ["NULL", "null"], ["상인", "商人", "🛒"], ["p", " p"]])
def test_valid_distinct_ids_and_existing_defaults_are_preserved(layout, identifiers):
    original = read_json(personas_path(PID))[0]
    people = [{**original, "id": identifier} for identifier in identifiers]
    # Historical valid records may omit optional fields.
    for person in people:
        person.pop("arrival_hour")
        person.pop("twin_of")
    write_json(personas_path(PID), people)
    before = personas_path(PID).read_bytes()
    loaded = [shelf_lab._personas(PID), run_estimate._inputs(PID, SID, "USD")[1],
              optimize._load_store_and_personas(PID, SID)[1],
              simulation._load_simulation_inputs(PID, read_setup(PID, SID), None)[2]]
    expected = [Persona.model_validate(p) for p in people]
    assert all(population == expected for population in loaded)
    assert all(len(simulation.subsample_personas(population, 1, 1)) == 1 for population in loaded)
    assert personas_path(PID).read_bytes() == before
