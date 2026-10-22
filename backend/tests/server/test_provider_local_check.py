"""A local server's saved address is not a running server: Settings says whether something answers there."""

import http.server
import threading

from fastapi.testclient import TestClient

from store_emulator.application import providers
from store_emulator.domain.providers import ProviderKind


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app

    return TestClient(app)


def _llamacpp(client: TestClient) -> dict[str, object]:
    return next(p for p in client.get("/api/providers").json() if p["preset"]["kind"] == "llamacpp")


def test_an_address_left_behind_with_nothing_listening_is_not_running(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    providers.update_provider(ProviderKind.LLAMACPP, providers.ProviderUpdate(enabled=True,
                                                                              api_base=f"http://127.0.0.1:{_free_port()}/v1"))
    status = _llamacpp(client)
    assert status["ready"] is True and status["answers"] is False


def test_a_server_that_answers_even_404_is_running(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    server = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)   # answers 501 to GET
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        providers.update_provider(ProviderKind.LLAMACPP, providers.ProviderUpdate(
            enabled=True, api_base=f"http://127.0.0.1:{server.server_address[1]}/v1"))
        assert _llamacpp(client)["answers"] is True
    finally:
        server.shutdown()


def test_cloud_and_turned_off_providers_are_not_checked(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    statuses = client.get("/api/providers").json()
    assert all(p["answers"] is None for p in statuses if not p["preset"]["local"] or not p["enabled"])
