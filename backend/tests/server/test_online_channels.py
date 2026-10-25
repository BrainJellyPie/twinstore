"""The same customers in both twins: an online run of the project's customers read next to a store run of them."""

import time

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"
STORE_RUN = "run_efd57c"  # the sample project's finished store run


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _run(client: TestClient, source: str) -> dict:  # type: ignore[type-arg]
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store"}).json()
    run = client.post(f"/api/projects/{PID}/online/runs", json={"site_ids": [site["id"]], "shoppers": 40, "source": source}).json()
    for _ in range(600):
        view = client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}").json()
        if view["status"]["status"] == "completed":
            return view
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_customers_split_into_store_online_both_and_neither(client: TestClient) -> None:
    view = _run(client, "project")
    run_id = view["result"]["run_id"]
    r = client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels")
    assert r.status_code == 200, r.text
    mix = r.json()
    assert mix["store_run_id"] == STORE_RUN and mix["online_store"] == view["result"]["variants"][0]["site_name"]
    assert mix["store_setup_id"].startswith("setup_")  # the layout to open the store run on
    assert 0 < mix["customers"] <= 40
    assert mix["both"] + mix["store_only"] + mix["online_only"] + mix["neither"] == mix["customers"]
    online_buyers = sum(1 for s in view["result"]["shoppers"]
                        if s["persona_id"] and view["result"]["visits"][s["id"]][0]["outcome"] == "purchased")
    assert mix["both"] + mix["online_only"] <= online_buyers
    assert sum(g["customers"] for g in mix["by_age"]) == mix["customers"] == sum(g["customers"] for g in mix["by_gender"])
    assert mix["store_spend"] >= 0 and mix["online_spend"] >= 0 and mix["store_currency"] and mix["online_currency"]
    assert client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels", params={"store_run": STORE_RUN}).json() == mix
    assert client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels", params={"store_run": "run_none"}).status_code == 404


def test_panel_shoppers_are_nobody_in_the_store(client: TestClient) -> None:
    run_id = _run(client, "panel")["result"]["run_id"]
    r = client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels")
    assert r.status_code == 400 and "built-in panel" in r.json()["detail"]


def test_no_store_run_of_these_customers_is_no_mix(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application import channels

    run_id = _run(client, "project")["result"]["run_id"]
    monkeypatch.setattr(channels, "_store_runs", lambda pid: [])
    r = client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels")
    assert r.status_code == 200 and r.json() is None


def test_the_online_analyst_reads_the_channel_mix(client: TestClient) -> None:
    run_id = _run(client, "project")["result"]["run_id"]
    facts = client.get(f"/api/projects/{PID}/online/runs/{run_id}/analyst/facts").text
    assert f"Store and online (the same " in facts and f"in store run {STORE_RUN}" in facts
    assert "Store and online by age:" in facts and "Store and online by gender:" in facts
    panel = _run(client, "panel")["result"]["run_id"]
    assert "Store and online" not in client.get(f"/api/projects/{PID}/online/runs/{panel}/analyst/facts").text


@pytest.mark.parametrize("kind", ["running_partial", "running_complete", "failed_complete", "completed_partial",
                                  "damaged_json", "missing_identity", "wrong_shape", "wrong_personas", "wrong_summary"])
def test_unusable_newer_store_run_does_not_hide_channels_or_analyst_facts(client, kind):
    import json
    from pathlib import Path
    from store_emulator.application import channels

    view = _run(client, "project")
    run_id = view["result"]["run_id"]
    url = f"/api/projects/{PID}/online/runs/{run_id}"
    expected = client.get(url + "/channels").json()
    base = Path(channels.DATA_DIR) / PID / "runs"
    newer = base / "run_partial"
    (newer / "output").mkdir(parents=True)
    (newer / "input").mkdir()
    if not kind.endswith("partial"):
        for name in ["output/timeline.json", "output/personas.json", "input/store.json", "output/summary.json"]:
            (newer / name).write_bytes((base / STORE_RUN / name).read_bytes())
    else:
        (newer / "output/timeline.json").write_text("[]")
    if kind == "damaged_json":
        (newer / "output/timeline.json").write_text("{")
    elif kind == "missing_identity":
        (newer / "output/timeline.json").write_text("[{}]")
    elif kind == "wrong_shape":
        (newer / "output/timeline.json").write_text("null")
    elif kind == "wrong_personas":
        (newer / "output/personas.json").write_text("[]")
    elif kind == "wrong_summary":
        (newer / "output/summary.json").write_text("[]")
    state = "running" if kind.startswith("running") else "failed" if kind.startswith("failed") else "completed"
    (newer / "status.json").write_text(json.dumps({"status": state, "created_at": "9999-01-01"}))
    assert client.get(url + "/channels").json() == expected
    facts = client.get(url + "/analyst/facts")
    assert facts.status_code == 200 and STORE_RUN in facts.text
    explicit = client.get(url + "/channels", params={"store_run": "run_partial"})
    assert explicit.status_code in {404, 409}


@pytest.mark.parametrize("status_text", [None, "{"])
def test_complete_legacy_store_run_remains_readable_without_good_status(client, status_text):
    from pathlib import Path
    from store_emulator.application import channels

    view = _run(client, "project")
    run_id = view["result"]["run_id"]
    url = f"/api/projects/{PID}/online/runs/{run_id}/channels"
    expected = client.get(url).json()
    status = Path(channels.DATA_DIR) / PID / "runs" / STORE_RUN / "status.json"
    if status_text is None:
        status.unlink()
    else:
        status.write_text(status_text)
    result = client.get(url, params={"store_run": STORE_RUN})
    assert result.status_code == 200
    assert result.json() == {**expected, "store_run_at": "", "store_setup_id": ""}
