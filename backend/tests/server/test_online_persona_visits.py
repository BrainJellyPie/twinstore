"""The same person in both twins: a project customer's online visits, from runs that drew shoppers from the
project's customers."""

import time

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _wait(client: TestClient, run_id: str) -> dict:  # type: ignore[type-arg]
    for _ in range(600):
        view = client.get(f"/api/projects/{PID}/online/runs/{run_id}").json()
        if view["status"]["status"] in ("completed", "failed"):
            return view
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_a_customers_online_visits_are_found_by_persona(client: TestClient) -> None:
    a = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    b = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    runs = f"/api/projects/{PID}/online/runs"
    panel = client.post(runs, json={"site_ids": [a["id"]], "shoppers": 6, "seed": 1}).json()
    status = client.post(runs, json={"site_ids": [a["id"], b["id"]], "shoppers": 8, "seed": 3, "source": "project",
                                      "name": "Customers online"}).json()
    _wait(client, panel["run_id"])
    result = _wait(client, status["run_id"])["result"]
    shopper = next(s for s in result["shoppers"] if s["persona_id"])
    visits = client.get(f"/api/projects/{PID}/online/personas/{shopper['persona_id']}/visits").json()
    mine = [v for v in visits if v["run_id"] == status["run_id"]]
    assert [v["variant"] for v in mine] == [0, 1] and all(v["shopper_id"] == shopper["id"] for v in mine)
    assert mine[0]["run_name"] == "Customers online" and mine[0]["site_name"] == result["variants"][0]["site_name"]
    for v in mine:
        brief = result["visits"][shopper["id"]][v["variant"]]
        assert v["outcome"] == brief["outcome"] and v["order_total"] == brief["order_total"]
    assert all(v["run_id"] != panel["run_id"] for v in visits)  # panel shoppers are nobody in particular
    assert client.get(f"/api/projects/{PID}/online/personas/nobody/visits").json() == []
