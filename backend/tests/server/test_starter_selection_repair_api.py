"""The wizard and existing-layout workflow recover an incomplete catalog response."""

import json

import pytest

from store_emulator.application import starter_fill, template_assortment
from store_emulator.application.storage.setups import read_setup, setup_path
from tests.engine.test_starter_selection_repair import RepairModel
from tests.server.test_project_templates import _meta, client
from tests.server.test_starter_fill_api import PID, SID, URL, automatic_request, workflow


@pytest.mark.parametrize("template", ["community_pharmacy", "specialty_cafe", "hypermarket"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_wizard_corrects_missing_sections_and_invalid_products_before_creating_project(client, monkeypatch, template, currency):
    api, generation = client
    model = RepairModel("missing_rack", "unknown_sku")
    monkeypatch.setattr(template_assortment, "assistive_client", lambda *args: model)
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(),
        "starter_selection": "automatic", "layout": {"template_id": template, "currency": currency,
        "products_per_category": 1, "excluded_categories": ["beer_alcohol"]},
    })})
    assert response.status_code == 200, response.text
    data = response.json()
    saved = read_setup(data["metadata"]["project_id"], data["setup"]["id"])
    assert model.counts == {"category": 2, "product": 1, "small": 1}
    assert saved["store"]["currency"] == currency
    assignments = saved["starter_selection"]["assignments"]
    assert assignments and all(row["category"] != "beer_alcohol" and len(row["skus"]) == 1 for row in assignments)
    assert {row["rack_id"] for row in assignments} == {r["id"] for r in saved["store"]["racks"] if any(s["items"] for s in r["slots"])}
    assert len(api.get("/api/projects").json()) == len(before) + 1
    generation.assert_called_once()


def test_persistent_incomplete_wizard_response_leaves_no_project_or_generation(client, monkeypatch):
    api, generation = client
    model = RepairModel("missing_rack", persistent=True)
    monkeypatch.setattr(template_assortment, "assistive_client", lambda *args: model)
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(),
        "starter_selection": "automatic", "layout": {"template_id": "community_pharmacy"},
    })})
    assert response.status_code == 502 and "format defaults" in response.text
    # This direct fake rejects invalid small replies during schema validation;
    # there is no additional outer semantic correction for the same batch.
    assert model.counts == {"category": 2, "small": 4}
    assert [len(payload["racks"]) for stage, payload in model.calls if stage == "small"] == [8, 4, 2, 1]
    assert api.get("/api/projects").json() == before
    generation.assert_not_called()


@pytest.mark.parametrize("change_during_correction", [False, True])
def test_existing_layout_repair_preserves_source_and_rechecks_changes(workflow, monkeypatch, change_during_correction):
    api, source = workflow
    path = setup_path(PID, SID)
    before = path.read_bytes()

    class Model(RepairModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if change_during_correction and "correction" in json.loads(user):
                from store_emulator.application.storage.io import write_json
                write_json(path, {**source, "store": {**source["store"], "name": "Changed during correction"}})
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = Model("duplicate_rack", "unknown_sku")
    monkeypatch.setattr(starter_fill, "assistive_client", lambda *args: model)
    response = api.post(URL + "/auto-select", json=automatic_request(api))
    assert response.status_code == (409 if change_during_correction else 200), response.text
    assert model.counts == {"category": 2, "product": 1, "small": 1}
    if change_during_correction:
        assert read_setup(PID, SID)["store"]["name"] == "Changed during correction"
    else:
        assert {row["rack_id"] for row in response.json()["assignments"]} == {"empty", "fridge"}
        assert api.post(URL + "/preview", json=response.json()).status_code == 200
        saved = api.post(URL + "/save", json={**response.json(), "request_id": "c" * 32})
        assert saved.status_code == 200, saved.text
        child = read_setup(PID, saved.json()["setup_id"])
        assert next(r for r in child["store"]["racks"] if r["id"] == "stocked") == next(r for r in source["store"]["racks"] if r["id"] == "stocked")
        assert path.read_bytes() == before
