"""Online model runs must not silently reinterpret shelf voting as a mixture."""

import pytest

from store_emulator.application import online
from tests.server.test_online_api import PID, client  # noqa: F401
from tests.engine.test_online_store import _FakeModel


@pytest.mark.parametrize("policy", ["vlm", "text"])
@pytest.mark.parametrize("mode", ["mixture", "vote"])
def test_online_runs_only_accept_the_ensemble_mode_they_execute(client, monkeypatch, policy, mode):
    calls = []
    monkeypatch.setattr(online, "ensure_resolvable", lambda _config: None)
    monkeypatch.setattr(online, "build_client", lambda *_args: calls.append("build") or _FakeModel())
    monkeypatch.setattr(online, "submit_background", lambda *_args: calls.append("submit"))
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    response = client.post(f"/api/projects/{PID}/online/runs", json={
        "site_ids": [site["id"]], "policy": policy, "model": "llamacpp:local",
        "ensemble": {"mode": mode, "members": [{"model": "llamacpp:local", "weight": 1}]},
    })
    if mode == "vote":
        assert response.status_code == 400
        assert "mixture" in response.text
        assert calls == []
        assert client.get(f"/api/projects/{PID}/online/runs").json() == []
    else:
        assert response.status_code == 200 and response.json()["status"] == "pending"
        assert calls == ["build", "submit"]
