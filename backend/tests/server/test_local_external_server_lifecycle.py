"""An adopted server can disappear without leaving its Start button disabled forever."""

import http.server
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm, providers
from store_emulator.application.hardware import HardwareProfile
from store_emulator.server.main import app


@pytest.fixture
def adopted(tmp_path, monkeypatch):
    state = {"reply": "ready", "calls": []}
    entered, release = threading.Event(), threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            state["calls"].append(self.path)
            if state["reply"] == "paused":
                entered.set()
                assert release.wait(5)
            if self.path == "/props":
                code, body = 200, {"total_slots": 2, "modalities": {"vision": True}}
            elif state["reply"] in {"unavailable", "paused"}:
                code, body = 503, {"error": "model unloaded"}
            elif state["reply"] == "webpage":
                code, body = 200, b"<html>another application</html>"
            else:
                code, body = 200, {"status": "ok"}
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
    thread.start()
    monkeypatch.setenv("PARASTORE_SETTINGS_DIR", str(tmp_path / "settings"))
    monkeypatch.delenv("TWINSTORE_LOCAL_VLM", raising=False)
    monkeypatch.setattr(local_vlm, "DEFAULT_PORT", server.server_port)
    mgr = local_vlm.LocalVLMManager(tmp_path / "local", hardware=lambda: HardwareProfile(os="linux", arch="x64"))
    monkeypatch.setattr(local_vlm, "_manager", [mgr])
    monkeypatch.setattr(providers, "cloud_providers_with_key", lambda: [])
    mgr.start(wait=True)
    assert mgr.status().state == "ready" and not mgr.status().managed
    assert mgr.status().slots == 2
    state["calls"].clear()
    try:
        yield mgr, server, state, entered, release
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("failure", ["closed", "unavailable", "webpage"])
@pytest.mark.parametrize("trigger", ["poll", "start"])
def test_missing_adopted_server_can_be_started_again(adopted, monkeypatch, failure, trigger):
    mgr, server, state, _, _ = adopted
    if failure == "closed":
        server.shutdown()
        server.server_close()
    else:
        state["reply"] = failure
    starts = []
    monkeypatch.setattr(mgr, "_runtime", lambda *args: mgr.home / "llama-server")
    monkeypatch.setattr(mgr, "_download_model", lambda *args: mgr.home / "test.gguf")
    # The known external endpoint is no longer a usable vision server.
    monkeypatch.setattr(local_vlm, "_serves_images", lambda base: False)

    def serve(*args):
        starts.append(True)
        mgr._ready("http://127.0.0.1:18081/v1", managed=True, runtime="fixture")

    monkeypatch.setattr(mgr, "_serve", serve)
    client = TestClient(app)
    if trigger == "poll":
        response = client.get("/api/system/models")
        assert response.status_code == 200
        assert response.json()["local"]["state"] == "error"
        assert response.json()["local"]["downloaded"] is False
        assert mgr.status().state == "error"
    response = client.post("/api/system/local-model/start")
    assert response.status_code == 200
    if mgr._thread is not None:
        mgr._thread.join(timeout=2)
        assert not mgr._thread.is_alive()
    assert starts == [True]
    assert mgr.status().state == "ready" and mgr.status().managed


def test_live_adopted_server_remains_ready_without_starting_another(adopted, monkeypatch):
    mgr, _, state, _, _ = adopted
    monkeypatch.setattr(mgr, "_runtime", lambda *args: pytest.fail("must reuse the answering server"))
    client = TestClient(app)
    assert client.get("/api/system/models").json()["local"]["state"] == "ready"
    assert client.post("/api/system/local-model/start").json()["state"] == "ready"
    assert not mgr.status().managed


@pytest.mark.parametrize("transition", ["unchanged", "starting", "disabled"])
def test_external_probe_leaves_health_and_status_available_and_preserves_new_state(adopted, transition):
    mgr, _, state, entered, release = adopted
    state["reply"] = "paused"
    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.get, "/api/system/models")
        try:
            assert entered.wait(2), "setup never checked the adopted endpoint"
            assert pool.submit(client.get, "/api/health").result(timeout=1).json() == {"status": "ok"}
            assert pool.submit(mgr.status).result(timeout=1).state == "ready"
            if transition != "unchanged":
                mgr._set(state=transition, message="new state")
        finally:
            release.set()
        result = pending.result(timeout=2)
    assert result.status_code == 200
    expected = "error" if transition == "unchanged" else transition
    assert result.json()["local"]["state"] == expected
    assert mgr.status().state == expected


def test_managed_process_status_does_not_probe_http(adopted):
    mgr, _, state, _, _ = adopted
    mgr._set(managed=True)
    state["reply"] = "unavailable"
    client = TestClient(app)
    assert client.get("/api/system/models").json()["local"]["state"] == "ready"
    assert client.post("/api/system/local-model/start").json()["state"] == "ready"
    assert state["calls"] == []
