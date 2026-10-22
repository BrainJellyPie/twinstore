"""Layout edits written in words: drafted on the layout's own products and shelves, checked on a copy, kept as a new
layout only when the user saves them (fake model, no network)."""

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


class _Editor:
    def __init__(self, draft: dict[str, object]) -> None:
        self.draft = draft
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate(self.draft)


def _store():
    from store_emulator.application.scenarios import (
        _store_for,  # pyright: ignore[reportPrivateUsage]
    )
    store = _store_for(PID, SETUP)
    assert store is not None
    return store


def _two_products():
    store = _store()
    seen: dict[str, tuple[str, str]] = {}
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                seen.setdefault(item.sku, (item.name, rack.rack_name))
    names = {}
    for sku, (name, rack) in seen.items():
        names.setdefault(name, []).append((sku, rack))
    unique = [(name, v[0][0], v[0][1]) for name, v in names.items() if len(v) == 1]
    return unique[0], unique[1], store


def test_instructions_become_checked_edits_and_a_new_layout(client, monkeypatch):
    from store_emulator.application import layout_edit
    (a_name, a_sku, _), (b_name, b_sku, b_rack), store = _two_products()
    fake = _Editor({"name": "Promo week", "summary": "A sign and a lower price.", "changes": [
        {"kind": "promo", "product": a_name, "promo": "SALE"},
        {"kind": "price", "product": b_name, "price": 0.99},
        {"kind": "move", "product": "Imaginary soda", "shelf": b_rack, "level": 3},
    ]})
    monkeypatch.setattr(layout_edit, "build_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit/draft", json={"text": "SALE sign on one, 99 cents for the other"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [c["kind"] for c in d["changes"]] == ["promo", "price"] and d["changes"][1]["price"] == 99
    assert len(d["applied"]) == 2 and any("Imaginary soda" in w for w in d["warnings"])
    assert "Instructions: SALE sign on one" in fake.calls[0][1]
    # Nothing was saved by drafting.
    before = {s["id"] for s in client.get(f"/api/projects/{PID}/setups").json()}
    saved = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit", json={"name": "Promo week", "changes": d["changes"]})
    assert saved.status_code == 200, saved.text
    new = saved.json()
    assert new["id"] not in before and new["name"] == "Promo week" and len(new["applied"]) == 2
    project = client.get(f"/api/projects/{PID}").json()
    assert project["state"]["activeSetupId"] == new["id"]
    detail = client.get(f"/api/projects/{PID}/setups/{new['id']}").json()
    items = {i["sku"]: i for r in detail["store"]["racks"] for s in r["slots"] for i in s["items"]}
    assert items[a_sku]["promo"] == "SALE" and items[b_sku]["price"] == 99
    # The original layout is unchanged.
    original = {i.sku: i for r in store.racks for s in r.slots for i in s.items}
    assert _store().model_dump() == store.model_dump() and original[b_sku].price != 99


def test_edits_that_fit_nothing_are_refused(client, monkeypatch):
    from store_emulator.application import layout_edit
    monkeypatch.setattr(layout_edit, "build_client", lambda *a, **k: _Editor({"name": "x", "changes": [
        {"kind": "promo", "product": "Imaginary soda", "promo": "NEW"}]}))
    r = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit/draft", json={"text": "NEW sign on the imaginary soda"})
    assert r.status_code == 502 and "could not be drafted" in r.json()["detail"]
    package = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit",
                          json={"changes": [{"kind": "package", "sku": "nothing", "asset_id": "pkg_x"}]})
    assert package.status_code == 422 and "only shown in tests" in package.json()["detail"]
