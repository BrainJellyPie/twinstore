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
def test_automatic_initial_products_use_wizard_category_before_project_and_personas_are_saved(client, monkeypatch, currency):
    from store_emulator.application import template_assortment
    from store_emulator.application.storage.setups import read_setup
    from store_emulator.engine.starter_selection import CategorySelection
    api, generation = client
    calls = []
    before = api.get("/api/projects").json()
    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            payload = json.loads(user); calls.append(payload)
            generation.assert_not_called()
            if issubclass(schema, CategorySelection):
                return schema.model_validate({"groups": [{"category": "first_aid_tools", "rack_ids": [r["id"] for r in payload["racks"]]}]})
            return schema.model_validate({"groups": [{"category": "first_aid_tools", "skus": [p["sku"] for p in payload["categories"]["first_aid_tools"][:2]]}]})
    monkeypatch.setattr(template_assortment, "assistive_client", lambda *a: Model())
    meta = {**_meta(), "starter_selection": "automatic", "layout": {"template_id": "community_pharmacy", "currency": currency}}
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(meta)})
    assert response.status_code == 200, response.text
    data = response.json(); pid, sid = data["metadata"]["project_id"], data["setup"]["id"]
    saved = read_setup(pid, sid)
    assert saved["starter_selection"]["mode"] == "automatic"
    assert saved["starter_selection"]["assignments"]
    assert all(row["category"] == "first_aid_tools" and len(row["skus"]) == 2 for row in saved["starter_selection"]["assignments"])
    assert calls[0]["store_name"] == meta["name"] and calls[0]["store_type"] == "pharmacy"
    assert "Care and wellness" in calls[0]["requirements"]
    assert len(calls) == 2 and len(api.get("/api/projects").json()) == len(before) + 1
    generation.assert_called_once()


@pytest.mark.parametrize("failure", ["timeout", "unknown_category", "unknown_sku", "excluded_category", "product_limit", "missing_model"])
def test_model_selection_failure_creates_no_partial_project_and_format_retry_succeeds(client, monkeypatch, failure):
    from store_emulator.application import template_assortment
    from store_emulator.engine.starter_selection import CategorySelection
    api, generation = client
    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            payload = json.loads(user)
            if failure == "timeout": raise TimeoutError("timed out")
            if issubclass(schema, CategorySelection):
                return schema.model_validate({"groups": [{"category": "unknown" if failure == "unknown_category" else "dairy", "rack_ids": [r["id"] for r in payload["racks"]]}]})
            return schema.model_validate({"groups": [{"category": "dairy", "skus": ["unknown"] if failure == "unknown_sku" else [p["sku"] for p in payload["categories"]["dairy"][:2]]}]})
    def client_factory(*args):
        if failure == "missing_model": raise ValueError("Set up a text model")
        return Model()
    monkeypatch.setattr(template_assortment, "assistive_client", client_factory)
    meta = {**_meta(), "starter_selection": "automatic", "layout": {"template_id": "community_pharmacy",
            "excluded_categories": ["dairy"] if failure == "excluded_category" else [], "products_per_category": 1 if failure == "product_limit" else 2}}
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(meta)})
    assert response.status_code == 502 and "format defaults" in response.text
    assert api.get("/api/projects").json() == before
    generation.assert_not_called()
    meta["starter_selection"] = "format"
    assert api.post("/api/projects/create-store", data={"meta": json.dumps(meta)}).status_code == 200
    generation.assert_called_once()


@pytest.mark.parametrize("value", ["AI", "unknown", True, 1, None])
def test_invalid_selection_mode_is_rejected_before_creation(client, value):
    api, generation = client
    before = api.get("/api/projects").json()
    assert api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(), "starter_selection": value})}).status_code == 422
    assert api.get("/api/projects").json() == before
    generation.assert_not_called()


def test_empty_start_does_not_call_product_model_even_when_automatic_is_requested(client, monkeypatch):
    from store_emulator.application import template_assortment
    api, generation = client
    def unexpected(*args):
        raise AssertionError("Empty layouts must not call the product model")
    monkeypatch.setattr(template_assortment, "assistive_client", unexpected)
    response = api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(), "starter_selection": "automatic"})})
    assert response.status_code == 200, response.text
    generation.assert_called_once()


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
