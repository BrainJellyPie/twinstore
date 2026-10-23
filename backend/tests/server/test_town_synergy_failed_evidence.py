from unittest.mock import Mock

from store_emulator.application import local_vlm, town_synergy
from tests.engine.test_reproducibility import _RecordingEngine
from tests.server.test_town_api import PID, client


class FailingEngine(_RecordingEngine):
    async def decide_actions(self, context):
        raise RuntimeError("offline customer failure")


def test_failed_customer_panel_does_not_publish_a_successful_zero_revenue_report(client, monkeypatch):
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: True)
    monkeypatch.setattr(town_synergy, "build_client", lambda *args: None)
    monkeypatch.setattr(town_synergy, "build_engine", lambda *args, **kwargs: FailingEngine())
    submit = Mock()
    monkeypatch.setattr(town_synergy.executor, "submit", submit)
    town = client.post(f"/api/projects/{PID}/town/generate", json={"seed": 4, "size_m": 400,
                      "n_competitors": 1, "venue_density": 0.0}).json()
    focal = next(v for v in town["venues"] if v["is_focal"])
    edited = client.post(f"/api/projects/{PID}/town/venues", json={"category": "cafe", "x": focal["x"] + 12,
                         "y": focal["y"], "name": "Neighbor"}).json()
    venue = next(v["id"] for v in edited["venues"] if v["name"] == "Neighbor")
    response = client.post(f"/api/projects/{PID}/town/venues/{venue}/synergy-vlm",
                           json={"customers": 4, "setup_id": "setup_7d6d"})
    assert response.status_code == 200, response.text
    job = response.json()["job_id"]
    function, *args = submit.call_args.args
    function(*args)
    view = client.get(f"/api/projects/{PID}/town/synergy-jobs/{job}").json()
    assert view["status"]["status"] == "failed"
    assert "No affected visitors completed" in view["status"]["error"]
    assert view["result"] is None
    assert not (town_synergy._dir(PID, job) / "result.json").exists()
