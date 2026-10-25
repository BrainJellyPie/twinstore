"""A shelf test drafted from a question: the product of the layout and its shelf, a library pack, a price in minor
units and a sign (fake model, no network)."""

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


def _layout_product():
    from store_emulator.application.scenarios import (
        _store_for,  # pyright: ignore[reportPrivateUsage]
    )
    store = _store_for(PID, SETUP)
    assert store is not None
    rack = store.product_racks[0]
    return rack, rack.slots[0].items[0]


@pytest.mark.parametrize("age", ["20s", " 20S "])
def test_a_question_becomes_a_builder_ready_shelf_test(client, monkeypatch, age):
    from store_emulator.application import shelf_lab, study_design
    rack, item = _layout_product()
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: [
        shelf_lab.PackageAsset(asset_id="pkg_gold", name="Gold label", width=10, height=10)])
    fake = _Designer({"name": "Gold label on the shelf", "product": f"{item.name} ($9.99, somewhere)", "package": "gold label",
                      "price": 1.49, "promo": "sale", "age_groups": [age], "rationale": "Pack, price and sign."})
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/shelf-tests/design", json={"question": "Would a gold label stand out?", "setup_id": SETUP})
    assert r.status_code == 200, r.text
    d = r.json()
    # The copied price and shelf after the name still resolve to the product and the shelf it stands on.
    assert d["target_sku"] == item.sku and d["rack_id"] == rack.id and d["age_groups"] == ["20s"]
    assert [c["kind"] for c in d["changes"]] == ["package", "price", "promo"]
    assert d["changes"][0]["asset_id"] == "pkg_gold" and d["changes"][1]["price"] == 149 and d["changes"][2]["promo"] == "SALE"
    assert "Product images: Gold label" in fake.calls[0][1]


def test_unknown_names_are_reported_or_refused(client, monkeypatch):
    from store_emulator.application import shelf_lab, study_design
    _, item = _layout_product()
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: [])
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: _Designer({
        "name": "x", "product": item.name, "package": "Moon pack", "price": None, "promo": ""}))
    d = client.post(f"/api/projects/{PID}/shelf-tests/design", json={"question": "Would a moon pack sell?", "setup_id": SETUP}).json()
    assert d["changes"] == [] and any("Moon pack" in w for w in d["warnings"]) and any("changes nothing" in w for w in d["warnings"])
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: _Designer({"name": "x", "product": "Imaginary soda", "promo": "NEW"}))
    r = client.post(f"/api/projects/{PID}/shelf-tests/design", json={"question": "Would a NEW sign help?", "setup_id": SETUP})
    assert r.status_code == 502 and "could not be drafted" in r.json()["detail"]


def test_repeated_sku_uses_the_requested_shelf_in_public_draft(client, monkeypatch):
    from store_emulator.application import shelf_lab, study_design
    from tests.engine.test_scenario_target_matching import target_store
    store = target_store()
    store.racks[1].slots[0].items.append(store.racks[0].slots[0].items[0].model_copy())
    monkeypatch.setattr(study_design, "_store_for", lambda *args: store)
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: [])
    monkeypatch.setattr(study_design, "assistive_client", lambda *args: _Designer(
        {"name": "Shelf test", "product": "Cola 500ml", "shelf": "Drinks 10", "promo": "SALE"}))
    response = client.post(f"/api/projects/{PID}/shelf-tests/design",
                           json={"question": "Test SALE on Cola at Drinks 10", "setup_id": SETUP})
    assert response.status_code == 200, response.text
    assert response.json()["rack_id"] == "r10" and response.json()["target_sku"] == "s-cola"


def test_an_ambiguous_product_name_is_not_guessed(client):
    from store_emulator.application.scenarios import (
        _store_for,  # pyright: ignore[reportPrivateUsage]
    )
    from store_emulator.engine.marketing.shelf_test_design import (
        _Draft,  # pyright: ignore[reportPrivateUsage]
        to_design,
    )
    _, item = _layout_product()
    store = _store_for(PID, SETUP)
    assert store is not None
    store = store.model_copy(deep=True)
    other = next(i for r in store.product_racks for s in r.slots for i in s.items if i.sku != item.sku)
    other.name = item.name
    with pytest.raises(ValueError, match="several products"):
        to_design(_Draft(name="x", product=item.name, promo="NEW"), store, "USD", [])
