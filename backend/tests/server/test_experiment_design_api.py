"""An A/B test drafted from a question, resolved to the layout's products and shelves (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Designer:
    def __init__(self, draft: dict[str, object]) -> None:
        self.draft = draft
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate(self.draft)


def _layout(client) -> tuple[dict, dict]:
    store = client.get(f"/api/projects/{PID}/setups/{SETUP}").json()["store"]
    rack = next(r for r in store["racks"] if r.get("slots"))
    item = rack["slots"][0]["items"][0]
    other = next(r for r in store["racks"] if r.get("slots") and r["id"] != rack["id"] and r.get("rack_name"))
    return item, other


def test_a_question_becomes_variants_on_the_layouts_products(client, monkeypatch):
    from store_emulator.application import study_design
    item, other = _layout(client)
    fake = _Designer({"name": "Sign or cut", "engine": "rule", "rationale": "Compare a sign with a price cut.",
                      "focus_products": [item["name"]], "variants": [
        {"name": "1+1 sign", "changes": [{"kind": "promo", "product": item["name"].lower(), "promo": "1+1"}]},
        {"name": "20 % off", "changes": [{"kind": "discount", "product": item["name"], "percent": -20}]},
        {"name": "Control", "changes": [{"kind": "price", "product": item["name"], "price": 1.79}]},
        {"name": "Eye level", "changes": [{"kind": "move", "product": item["name"], "shelf": other["rack_name"], "level": 3},
                                          {"kind": "promo", "product": "Unicorn Milk"}]},
        {"name": "Ghost", "changes": [{"kind": "move", "product": item["name"], "shelf": "Nowhere"}]},
    ]})
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/experiments/design", json={"question": "Does a 1+1 sign beat a 20 % cut?", "setup_id": SETUP})
    assert r.status_code == 200, r.text
    d = r.json()
    names = [v["name"] for v in d["variants"]]
    assert names == ["1+1 sign", "20 % off", "Control (4)", "Eye level"]
    assert d["variants"][0]["changes"][0] == {**d["variants"][0]["changes"][0], "kind": "promo", "sku": item["sku"], "promo": "1+1"}
    assert d["variants"][2]["changes"][0]["price"] == 179 and d["variants"][2]["changes"][0]["keep_reference"]
    assert d["variants"][3]["changes"][0]["rack_id"] == other["id"] and len(d["variants"][3]["changes"]) == 1
    assert d["focus_skus"] == [item["sku"]] and d["engine"] == "rule"
    assert any("Unicorn Milk" in w for w in d["warnings"]) and any("Nowhere" in w for w in d["warnings"])
    assert any("Ghost" in w and "left out" in w for w in d["warnings"])
    system, user = fake.calls[0]
    assert "major units of USD" in system and "Products: " in user and "Shelves: " in user
    assert "sold in the last run" in user  # the sample layout has a final run, so sales are listed
    # The draft is a valid request as it stands.
    from store_emulator.domain.marketing import ExperimentRequest
    ExperimentRequest.model_validate({"setup_id": SETUP, "name": d["name"], "variants": d["variants"],
                                      "focus_skus": d["focus_skus"], "engine": d["engine"], "panel": 20})


def test_a_draft_with_nothing_usable_is_an_error(client, monkeypatch):
    from store_emulator.application import study_design
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: _Designer({"name": "x", "variants": [
        {"name": "A", "changes": [{"kind": "promo", "product": "Unicorn Milk"}]}]}))
    r = client.post(f"/api/projects/{PID}/experiments/design", json={"question": "Unicorn milk deal?", "setup_id": SETUP})
    assert r.status_code == 502 and "could not be drafted" in r.json()["detail"]
    assert client.post(f"/api/projects/{PID}/experiments/design", json={"question": "Deal?", "setup_id": "nope"}).status_code == 404
