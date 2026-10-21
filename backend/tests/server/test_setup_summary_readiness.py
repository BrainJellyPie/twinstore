"""Layout summaries and detail views must describe the same simulation prerequisites."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.generations import init_generation
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import (
    list_setups, metadata_path, new_setup_data, personas_path, setup_path, write_setup,
)
from store_emulator.domain.persona import Persona
from store_emulator.engine.layout_gen import generate_store

PID = "proj_readiness"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(metadata_path(PID), {"project_id": PID, "name": "Readiness", "store_type": "cafe",
                                  "created_at": "2026-10-21", "updated_at": "2026-10-21"})
    persona = Persona(id="p_test", identity="Reader", age_group="30s", gender="Female",
                      description="Visits a book café", intent="coffee", purpose="break")
    write_json(personas_path(PID), [persona.model_dump(mode="json")])
    store = generate_store("book_cafe")
    unstocked = store.model_copy(deep=True)
    for rack in unstocked.racks:
        for slot in rack.slots:
            slot.items = []
    for sid, model in [("setup_ready", store), ("setup_unstocked", unstocked), ("setup_empty", None)]:
        setup = new_setup_data(sid, None, model.model_dump(mode="json") if model else None)
        setup["id"] = sid
        write_setup(PID, sid, setup)
    from store_emulator.server.main import app
    # No startup bootstrap or background jobs are needed for these read-only routes.
    return TestClient(app)


def test_list_and_project_summaries_match_details_without_exposing_or_rewriting_stores(client):
    before = setup_path(PID, "setup_ready").read_bytes()
    summaries = client.get(f"/api/projects/{PID}/setups").json()
    project = client.get(f"/api/projects/{PID}").json()
    expected = {"setup_ready": [], "setup_unstocked": ["no_items"], "setup_empty": ["no_layout"]}
    for summary in summaries:
        detail = client.get(f"/api/projects/{PID}/setups/{summary['id']}").json()
        assert summary["readiness"] == detail["readiness"]
        assert summary["readiness"]["reasons"] == expected[summary["id"]]
        assert "store" not in summary
        assert next(s for s in project["setups"] if s["id"] == summary["id"])["readiness"] == detail["readiness"]
    assert all("store" not in setup for setup in list_setups(PID))
    assert setup_path(PID, "setup_ready").read_bytes() == before


@pytest.mark.parametrize("state,reason", [
    ("missing_personas", "no_personas"), ("persona", "personas_pending"), ("layout", "layout_pending"),
])
def test_summary_readiness_preserves_shared_and_floor_specific_generation_states(client, state, reason):
    if state == "missing_personas":
        write_json(personas_path(PID), [])
    else:
        init_generation(PID, "setup_ready", state)
    summaries = client.get(f"/api/projects/{PID}/setups").json()
    for summary in summaries:
        detail = client.get(f"/api/projects/{PID}/setups/{summary['id']}").json()
        assert summary["readiness"] == detail["readiness"]
        assert (reason in summary["readiness"]["reasons"]) == (state != "layout" or summary["id"] == "setup_ready")
