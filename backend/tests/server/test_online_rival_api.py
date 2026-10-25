"""A run with a rival shop: the visits of shoppers who leave without buying, and what each store lost to it."""

import csv
import io
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


def _site(client: TestClient, template: str, **options: object) -> dict:  # type: ignore[type-arg]
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": template}).json()
    site = {**site, "options": {**site["options"], "welcome_popup": "none", **options}}
    return client.put(f"/api/projects/{PID}/online/sites/{site['id']}", json=site).json()


def test_shoppers_who_leave_try_the_rival_once_and_each_store_sees_what_it_lost(client: TestClient) -> None:
    control = _site(client, "pet_store")
    worse = _site(client, "pet_store", service_fee=900, guest_checkout=False)
    rival = _site(client, "pet_store")
    runs = f"/api/projects/{PID}/online/runs"
    # Shoppers who came to buy, so that a worse store has orders to lose (the default mix is nearly all window shoppers).
    missions = {"purchase": 0.25, "browse": 0.35, "compare": 0.15, "deal_hunt": 0.1, "gift": 0.07, "replenish": 0.08}
    body = {"site_ids": [control["id"], worse["id"]], "shoppers": 40, "seed": 3, "max_steps": 30, "missions": missions}
    assert client.post(runs, json={**body, "rival_site_id": control["id"]}).status_code == 400
    status = client.post(runs, json={**body, "rival_site_id": rival["id"]}).json()
    assert status["total"] == 40 * 3
    view = _wait(client, status["run_id"])
    assert view["status"]["status"] == "completed", view["status"]["error"]
    result = view["result"]
    assert result["rival_name"] == rival["name"]

    def visits(variant: int) -> dict[str, dict]:  # type: ignore[type-arg]
        return {s["id"]: client.get(f"{runs}/{status['run_id']}/sessions/{variant}/{s['id']}").json()
                for s in result["shoppers"]}

    first, second, at_rival = visits(0), visits(1), visits(2)
    went = {i for i, v in at_rival.items() if v.get("session")}
    assert went and all(v["site_name"] == rival["name"] for i, v in at_rival.items() if i in went)
    for i in went:
        assert at_rival[i]["shopper"]["arrival"] == "search_engine"
        assert at_rival[i]["session"]["steps"][0]["page"] == "product"
        assert at_rival[i]["session"]["survey"] is None
    for store in (first, second):
        for i, view_ in store.items():
            session = view_["session"]
            if session["outcome"] == "purchased":
                assert session["rival"] is None
            elif i in went:
                rival_session = at_rival[i]["session"]
                assert session["rival"]["outcome"] == rival_session["outcome"]
                assert session["rival"]["order_total"] == rival_session["order_total"]
            else:
                assert session["rival"] is None
    rows = [v["rival"] for v in result["variants"]]
    for row, store in zip(rows, (first, second), strict=True):
        lost = [v["session"] for v in store.values() if v["session"]["outcome"] != "purchased"]
        assert row["left"] == len(lost) and row["went"] == sum(s["rival"] is not None for s in lost)
        assert row["revenue"] == sum(s["rival"]["order_total"] for s in lost if s["rival"] is not None)
    # A worse store loses more shoppers, and the rival takes more from it, measured on the same shoppers.
    assert rows[1]["left"] > rows[0]["left"] and rows[1]["revenue"] >= rows[0]["revenue"]
    delta = next(d for d in result["comparisons"][0]["deltas"] if d["metric"] == "rival_revenue_per_session")
    assert delta["diff"] == pytest.approx((rows[1]["revenue"] - rows[0]["revenue"]) / 40, abs=1e-3)

    some = next(iter(went))
    shot = client.get(f"{runs}/{status['run_id']}/sessions/2/{some}/steps/0.png")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"
    assert client.get(f"{runs}/{status['run_id']}/sessions/3/{some}").status_code == 404
    csv_rows = list(csv.DictReader(io.StringIO(client.get(f"{runs}/{status['run_id']}/clickstream.csv").text.lstrip("\ufeff"))))
    at_rival_rows = [row for row in csv_rows if row["variant"] == "2"]
    assert at_rival_rows and all(row["site"] == rival["name"] and row["arrival"] == "search_engine" for row in at_rival_rows)


def test_a_rival_must_use_the_same_currency(client: TestClient) -> None:
    sites = []
    for currency in ("USD", "KRW"):
        layout = client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "specialty_cafe", "currency": currency})
        sites.append(client.post(f"/api/projects/{PID}/online/sites",
                                 json={"template_id": "from_store", "setup_id": layout.json()["id"]}).json())
    run = client.post(f"/api/projects/{PID}/online/runs",
                      json={"site_ids": [sites[0]["id"]], "shoppers": 5, "rival_site_id": sites[1]["id"]})
    assert run.status_code == 400 and "same currency" in run.text
    assert client.get(f"/api/projects/{PID}/online/runs").json() == []


def test_a_rival_visit_is_a_new_visit_not_a_replay_of_the_one_left(client: TestClient) -> None:
    # A rival exactly like the store, reached the way the shoppers reached it (a search engine): on shared random
    # numbers every lost shopper would leave it the same way.
    control, rival = _site(client, "pet_store"), _site(client, "pet_store")
    runs = f"/api/projects/{PID}/online/runs"
    status = client.post(runs, json={"site_ids": [control["id"]], "rival_site_id": rival["id"], "shoppers": 60, "seed": 4,
                                      "max_steps": 30, "missions": {"purchase": 1.0},
                                      "arrivals": {"search_engine": 1.0}}).json()
    view = _wait(client, status["run_id"])
    assert view["status"]["status"] == "completed", view["status"]["error"]
    row = view["result"]["variants"][0]["rival"]
    assert row["went"] >= 10 and row["bought"] > 0
    replayed = 0
    for shopper in view["result"]["shoppers"]:
        there = client.get(f"{runs}/{status['run_id']}/sessions/1/{shopper['id']}")
        if there.status_code != 200:
            continue
        here = client.get(f"{runs}/{status['run_id']}/sessions/0/{shopper['id']}").json()["session"]
        pick = lambda s: [(step["url"], step["choice"] and step["choice"]["label"]) for step in s["steps"]]  # noqa: E731
        replayed += pick(here) == pick(there.json()["session"])
    assert replayed < row["went"] / 2


def test_a_run_lists_how_each_shoppers_visits_ended(client: TestClient) -> None:
    control, worse, rival = _site(client, "pet_store"), _site(client, "pet_store", service_fee=900), _site(client, "pet_store")
    runs = f"/api/projects/{PID}/online/runs"
    status = client.post(runs, json={"site_ids": [control["id"], worse["id"]], "rival_site_id": rival["id"], "shoppers": 12,
                                      "seed": 2, "max_steps": 30}).json()
    result = _wait(client, status["run_id"])["result"]
    assert set(result["visits"]) == {s["id"] for s in result["shoppers"]}
    for shopper in result["shoppers"]:
        briefs = result["visits"][shopper["id"]]
        assert len(briefs) == 2
        for variant, brief in enumerate(briefs):
            session = client.get(f"{runs}/{status['run_id']}/sessions/{variant}/{shopper['id']}").json()["session"]
            assert brief["outcome"] == session["outcome"] and brief["order_total"] == session["order_total"]
            assert brief["clicks"] == sum(1 for step in session["steps"] if step["choice"])
            assert brief["rival"] == (session["rival"]["outcome"] if session["rival"] else None)
            stages = ["visit", "product_view", "add_to_cart", "checkout", "payment", "purchase"]
            assert brief["furthest"] == max(session["reached"], key=stages.index)


def test_the_page_flow_follows_every_visit_to_its_end(client: TestClient) -> None:
    store = _site(client, "pet_store")
    runs = f"/api/projects/{PID}/online/runs"
    status = client.post(runs, json={"site_ids": [store["id"]], "shoppers": 15, "seed": 4, "max_steps": 30}).json()
    summary = _wait(client, status["run_id"])["result"]["variants"][0]
    flow = summary["flow"]
    ends = [link for link in flow if link["target"] is None]
    assert sum(link["sessions"] for link in ends) == summary["sessions"]
    for outcome, count in summary["outcomes"].items():
        assert sum(link["sessions"] for link in ends if link["outcome"] == outcome) == count
    # Visits flow on: what enters a page at one step leaves it at that step, to the next page or the end.
    for depth in range(1, 6):
        for page in {link["source"] for link in flow if link["depth"] == depth}:
            into = sum(link["sessions"] for link in flow if link["depth"] == depth - 1 and link["target"] == page)
            out = sum(link["sessions"] for link in flow if link["depth"] == depth and link["source"] == page)
            assert into == out
    assert max(link["depth"] for link in flow) <= 5
