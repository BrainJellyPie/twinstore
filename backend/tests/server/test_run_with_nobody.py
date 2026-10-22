"""A run that simulated nobody fails with a reason instead of finishing "completed" and locking the layout."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _new_layout(c: TestClient) -> str:
    return c.post(f"/api/projects/{PID}/setups", json={"mode": "racks_and_items", "source_setup_id": "setup_7d6d"}).json()["id"]


def _finish(c: TestClient, rid: str) -> dict[str, object]:
    for _ in range(600):
        st = c.get(f"/api/projects/{PID}/runs/{rid}/status").json()
        if st["status"] in ("completed", "failed"):
            return st
        time.sleep(0.05)
    raise AssertionError("the run did not finish")


def test_every_shopper_failing_fails_the_run_and_keeps_the_layout_editable(client, monkeypatch):
    from store_emulator.engine.simulation.engines import rule_based

    async def refused(self, context):  # noqa: ANN001, ANN202
        raise RuntimeError("AuthenticationError: invalid api key")

    monkeypatch.setattr(rule_based.RuleBasedEngine, "decide_actions", refused)
    sid = _new_layout(client)
    rid = client.post(f"/api/projects/{PID}/runs", json={"setup_id": sid, "engine_type": "rule_based", "max_customers": 6}).json()["run_id"]
    st = _finish(client, rid)
    assert st["status"] == "failed"
    assert str(st["error"]).startswith("All 6 shoppers failed, so nothing was simulated: the provider rejected the API key")
    time.sleep(0.2)
    layout = client.get(f"/api/projects/{PID}/setups/{sid}").json()
    assert layout["status"] == "draft" and not layout.get("runId")


def test_no_shopper_on_the_scenarios_days_fails_the_run(client):
    sid = _new_layout(client)
    path = Path(f".data/{PID}/setups/{sid}.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    for day in data["store"]["weekly_schedule"]:
        day["is_open"] = day["day"] in (6, 7)          # a weekend-only store…
    path.write_text(json.dumps(data), encoding="utf-8")
    rid = client.post(f"/api/projects/{PID}/runs",
                      json={"setup_id": sid, "engine_type": "rule_based", "scenario_id": "payday_friday"}).json()["run_id"]
    st = _finish(client, rid)                           # …and a Friday-night scenario
    assert st["status"] == "failed" and str(st["error"]).startswith("No shoppers come on this scenario's days")
    time.sleep(0.2)
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "draft"
