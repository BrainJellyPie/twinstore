"""Shoppers found from a sentence: the model writes the filter, the run's records decide who fits (fake model)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"
RUN = "run_efd57c"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Finder:
    def __init__(self, f: dict[str, object]) -> None:
        self.f = f
        self.prompts: list[str] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.prompts.append(user_prompt)
        return response_model.model_validate(self.f)


def _run():
    from store_emulator.application.interview import (
        _load,  # pyright: ignore[reportPrivateUsage]
    )
    return _load(PID, RUN)


def _find(client, monkeypatch, f: dict[str, object], text: str = "some shoppers"):
    from store_emulator.application import shopper_search
    fake = _Finder(f)
    monkeypatch.setattr(shopper_search, "build_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/shoppers/find", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json(), fake


def test_every_listed_shopper_fits_the_filter(client, monkeypatch):
    customers, personas, store, _ = _run()
    rack = next(r for r in store.product_racks if r.rack_name)
    d, fake = _find(client, monkeypatch, {
        "label": "Afternoon browsers", "genders": ["Female"], "bought": "no", "stopped_at": [rack.rack_name, "Moon shelf"],
        "arrived_after": "12:00", "sort": "nothing",
    }, "women who stopped but bought nothing after noon")
    assert d["total"] == len(customers) and any("Moon shelf" in w for w in d["warnings"])
    assert d["criteria"] == ["Gender: Female", "Bought nothing", f"Stopped at {rack.rack_name}", "Arrived at or after 12:00"]
    for pid in d["persona_ids"]:
        c = customers[pid]
        assert personas[pid].gender == "Female" and not c.purchases and c.arrival_time[:5] >= "12:00"
        assert any(e.target_rack == rack.id for e in c.timeline)
    # Nobody who fits was left out.
    expected = {pid for pid, c in customers.items() if personas[pid].gender == "Female" and not c.purchases
                and c.arrival_time[:5] >= "12:00" and any(e.target_rack == rack.id and e.action.value in ("browse", "buy") for e in c.timeline)}
    assert set(d["persona_ids"]) == expected
    assert "Shoppers wanted: women who stopped" in fake.prompts[0]


def test_spend_products_and_sorting(client, monkeypatch):
    customers, _, _, _ = _run()
    buyer = max(customers.values(), key=lambda c: c.total_spent)
    product = buyer.purchases[0].product_name
    d, _ = _find(client, monkeypatch, {"label": "Big baskets", "bought_products": [product], "min_spent": 1.0, "sort": "spent"})
    spent = [customers[p].total_spent for p in d["persona_ids"]]
    assert d["persona_ids"][0] == buyer.persona_id and spent == sorted(spent, reverse=True) and min(spent) >= 100
    assert all(any(e.product_name == product for e in customers[p].purchases) for p in d["persona_ids"])


def test_a_failed_model_is_explained(client, monkeypatch):
    from store_emulator.application import shopper_search
    monkeypatch.setattr(shopper_search, "build_client", lambda *a, **k: _Finder({"label": "x", "sort": "random"}))
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/shoppers/find", json={"text": "anyone"})
    assert r.status_code == 502 and "could not be found" in r.json()["detail"]
    assert client.post(f"/api/projects/{PID}/runs/run_missing/shoppers/find", json={"text": "anyone"}).status_code == 404


def test_shelves_and_products_match_any_of_those_listed(client, monkeypatch):
    customers, _, store, _ = _run()
    a, b = [r for r in store.product_racks if r.rack_name][:2]
    d, _ = _find(client, monkeypatch, {"label": "Either shelf", "stopped_at": [a.rack_name, b.rack_name]})
    visited = {pid for pid, c in customers.items() if any(e.target_rack in (a.id, b.id) and e.action.value in ("browse", "buy") for e in c.timeline)}
    assert set(d["persona_ids"]) == visited and d["criteria"] == [f"Stopped at {a.rack_name} or {b.rack_name}"]


def test_bought_nothing_there_is_about_the_shelves_not_the_trip(client, monkeypatch):
    customers, _, store, _ = _run()
    rack = next(r for r in store.product_racks if r.rack_name)
    d, _ = _find(client, monkeypatch, {"label": "Looked, left it", "stopped_at": [rack.rack_name], "bought_there": "no"})
    for pid in d["persona_ids"]:
        c = customers[pid]
        assert any(e.target_rack == rack.id for e in c.timeline) and not any(e.target_rack == rack.id for e in c.purchases)
    assert d["criteria"] == [f"Stopped at {rack.rack_name}", f"Bought nothing at {rack.rack_name}"]


def test_bought_nothing_twice_means_there_and_empty_results_say_what_blocks_them(client, monkeypatch):
    _, _, store, _ = _run()
    rack = next(r for r in store.product_racks if r.rack_name)
    d, _ = _find(client, monkeypatch, {"label": "x", "stopped_at": [rack.rack_name], "bought": "no", "bought_there": "no"})
    assert "Bought nothing" not in d["criteria"] and any("bought nothing at all" in w for w in d["warnings"])
    d, _ = _find(client, monkeypatch, {"label": "x", "bought": "no", "min_spent": 1.0})
    assert d["persona_ids"] == [] and d["near_misses"]
    assert any(m.startswith('Without "Bought nothing": ') for m in d["near_misses"])
