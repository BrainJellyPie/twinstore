"""The reported local-model failure recovers before any project is committed."""

import json

import pytest

from store_emulator.application import template_assortment
from store_emulator.application.storage.setups import read_setup
from tests.engine.test_starter_selection_small_tasks import SmallTaskModel
from tests.server.test_project_templates import _meta, client


@pytest.mark.parametrize("template", ["specialty_cafe", "hypermarket"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("max_rows", [1, 8])
def test_wizard_recovers_repeated_invented_sections_and_skus(client, monkeypatch, template, currency, max_rows):
    api, generation = client
    class LimitedRows(SmallTaskModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            payload = json.loads(user)
            if "choices" in schema.model_fields and "racks" in payload and len(payload["racks"]) > max_rows:
                self.calls.append((schema, payload, system))
                return schema.model_validate({"choices": ["home_coffee_tea"]})
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = LimitedRows()
    monkeypatch.setattr(template_assortment, "assistive_client", lambda *args: model)
    response = api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(),
        "starter_selection": "automatic", "customer_profile": "동네 주민",
        "layout": {"template_id": template, "currency": currency, "excluded_categories": ["beer_alcohol"],
                   "products_per_category": 1},
    })})
    assert response.status_code == 200, response.text
    data = response.json()
    setup = read_setup(data["metadata"]["project_id"], data["setup"]["id"])
    assignments = setup["starter_selection"]["assignments"]
    assert assignments and all(r["category"] == "home_coffee_tea" and len(r["skus"]) == 1 for r in assignments)
    assert {r["rack_id"] for r in assignments} == {r["id"] for r in setup["store"]["racks"] if any(s["items"] for s in r["slots"])}
    assert setup["store"]["currency"] == currency
    generation.assert_called_once()


def test_failed_recovery_does_not_create_project_or_start_customer_generation(client, monkeypatch):
    api, generation = client
    monkeypatch.setattr(template_assortment, "assistive_client", lambda *args: SmallTaskModel(bad_small="unknown"))
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(),
        "starter_selection": "automatic", "layout": {"template_id": "specialty_cafe"},
    })})
    assert response.status_code == 502
    assert api.get("/api/projects").json() == before
    generation.assert_not_called()
