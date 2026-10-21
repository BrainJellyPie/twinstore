"""The project wizard creates a usable first layout without a second store-generation call."""

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.application import projects
    generation = Mock(return_value="gen_test")
    monkeypatch.setattr(projects, "start_persona_generation", generation)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client, generation


def _meta():
    return {"name": "Neighborhood Pharmacy", "description": "Care and wellness",
            "address": "12 Market Street", "store_type": "pharmacy", "customer_profile": "Nearby residents",
            "weekly_schedule": [{"day": 1, "is_open": True, "open_hour": 9, "close_hour": 19}]}


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_initial_layout_respects_wizard_name_hours_and_options(client, currency):
    api, generation = client
    meta = {**_meta(), "layout": {"template_id": "community_pharmacy", "width": 22, "height": 18,
                                 "style": "spine", "design_theme": "botanical", "checkouts": 2, "currency": currency}}
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(meta)})
    assert response.status_code == 200, response.text
    result = response.json()
    pid, sid = result["metadata"]["project_id"], result["setup"]["id"]
    setup = api.get(f"/api/projects/{pid}/setups/{sid}").json()
    store = setup["store"]
    assert store["name"] == meta["name"]
    assert store["type"] == meta["store_type"]
    assert store["weekly_schedule"] == meta["weekly_schedule"]
    assert store["grid_size"] == result["metadata"]["grid_size"] == [22, 18]
    assert store["design_theme"] == "botanical"
    assert store["currency"] == result["metadata"]["currency"] == currency
    assert sum(r["type"] == "counter" for r in store["racks"]) == 2
    assert setup["generation"]["template_id"] == "community_pharmacy"
    assert len(api.get(f"/api/projects/{pid}/setups").json()) == 1
    generation.assert_called_once()
    assert generation.call_args.kwargs["setup_id"] == sid
    assert generation.call_args.kwargs["config"].currency == currency


def test_legacy_wizard_can_still_start_with_an_empty_layout(client):
    api, generation = client
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(_meta())})
    assert response.status_code == 200, response.text
    result = response.json()
    setup = api.get(f"/api/projects/{result['metadata']['project_id']}/setups/{result['setup']['id']}").json()
    assert setup["store"] is None
    generation.assert_called_once()


@pytest.mark.parametrize("layout,status", [({"template_id": "not-a-store"}, 404),
                                           ({"template_id": "urban_cvs", "width": 99}, 422),
                                           ({"template_id": "specialty_cafe", "width": 8, "height": 6, "dining_tables": 12}, 422)])
def test_invalid_initial_layout_creates_no_project_or_persona_job(client, layout, status):
    api, generation = client
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(), "layout": layout})})
    assert response.status_code == status, response.text
    assert api.get("/api/projects").json() == before
    generation.assert_not_called()
