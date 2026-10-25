"""An alternative staff script drafted for the same product and offer (fake model, no network)."""

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


def test_a_script_is_drafted_with_the_offer_and_only_the_given_facts(client, monkeypatch):
    from store_emulator.application import staff_pitch
    store = client.get(f"/api/projects/{PID}/setups/{SETUP}").json()["store"]
    item = next(i for r in store["racks"] for s in r.get("slots", []) for i in s["items"])
    seen: list[tuple[str, str]] = []

    class _Writer:
        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            seen.append((system_prompt, user_prompt))
            return response_model.model_validate({"name": "Value first", "script": "Hi!   This one is   a good deal today.",
                                                  "differs_by": "Leads with value."})

    monkeypatch.setattr(staff_pitch, "build_client", lambda *a, **k: _Writer())

    monkeypatch.setattr(staff_pitch, "assistive_client", lambda *a, **k: _Writer())
    r = client.post(f"/api/projects/{PID}/staff-pitches/draft-script", json={
        "setup_id": SETUP, "sku": item["sku"], "context": "Shopper at the shelf.", "product_facts": "500 ml.",
        "current": "Can I help you?", "direction": "lead with value"})
    assert r.status_code == 200, r.text
    assert r.json() == {"name": "Value first", "script": "Hi! This one is a good deal today.", "differs_by": "Leads with value."}
    system, user = seen[0]
    assert "Keep the same product, price and promotion" in system
    assert f"Product: {item['name']}. Offer on the shelf: $" in user and "Verified facts: 500 ml." in user
    assert "Current script: Can I help you?" in user and user.endswith("Direction: lead with value")
    bad = client.post(f"/api/projects/{PID}/staff-pitches/draft-script", json={"setup_id": SETUP, "sku": "NOPE"})
    assert bad.status_code == 400


@pytest.mark.parametrize("difference", ["name", "price", "promo", "identical", "other-sku"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("reverse", [False, True])
def test_drafts_require_one_unambiguous_offer_before_calling_the_model(client, monkeypatch, difference, currency, reverse):
    from store_emulator.application import staff_pitch
    from store_emulator.application.storage.io import read_json, write_json
    from store_emulator.application.storage.setups import metadata_path
    from store_emulator.engine.prompting import display_price
    from tests.engine.test_layout_applied_changes import fixture

    store, _ = fixture("valid")
    store.currency = currency
    meta = metadata_path(PID)
    write_json(meta, {**read_json(meta), "currency": currency})
    item = store.racks[1].slots[0].items[0]
    item.price = 199 if currency == "USD" else 2000
    item.promo = "SALE"
    second = item.model_copy(deep=True)
    if difference == "name":
        second.name = "Different tea"
    elif difference == "price":
        second.price = 0
    elif difference == "promo":
        second.promo = "1+1"
    elif difference == "other-sku":
        second.sku, second.name, second.price, second.promo = "other", "Other tea", 0, "1+1"
    store.racks[2].slots[0].items.append(second)
    if reverse:
        store.racks.reverse()
    before = store.model_dump_json()
    monkeypatch.setattr(staff_pitch, "_load_store", lambda *args: store)
    clients, prompts = [], []

    class Writer:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            prompts.append(user)
            return schema.model_validate({"name": "Offer", "script": "Would you like this tea?"})

    def make_client(*args):
        clients.append(args)
        return Writer()

    monkeypatch.setattr(staff_pitch, "assistive_client", make_client)
    response = client.post(f"/api/projects/{PID}/staff-pitches/draft-script", json={"setup_id": SETUP, "sku": "tea"})
    if difference in {"name", "price", "promo"}:
        assert response.status_code == 400, response.text
        assert "conflicting" in response.json()["detail"]
        assert not clients and not prompts
    else:
        assert response.status_code == 200, response.text
        assert len(clients) == len(prompts) == 1
        assert f"Product: Tea. Offer on the shelf: {display_price(item.price, currency)}, promotion 'SALE'." in prompts[0]
    assert store.model_dump_json() == before
