"""Model discovery and provider persistence must not stall the server event loop."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Event

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm, providers
from store_emulator.domain.providers import ProviderKind
from store_emulator.server.main import app


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PARASTORE_SETTINGS_DIR", str(tmp_path / "settings"))
    manager = local_vlm.LocalVLMManager(tmp_path / "local")
    manager._set(state="off")
    monkeypatch.setattr(local_vlm, "_manager", [manager])

    @asynccontextmanager
    async def no_startup(_app):
        yield

    monkeypatch.setattr(app.router, "lifespan_context", no_startup)


@pytest.mark.parametrize("answers", [False, True])
def test_slow_local_model_discovery_keeps_health_available(isolated_settings, monkeypatch, answers):
    endpoint = "http://127.0.0.1:8081/v1"
    providers.update_provider(ProviderKind.LLAMACPP, providers.ProviderUpdate(enabled=True, api_base=endpoint))
    started, release = Event(), Event()

    def delayed_health(base):
        assert base == endpoint
        started.set()
        assert release.wait(5)
        return answers

    monkeypatch.setattr(local_vlm, "server_answers", delayed_health)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.get, "/api/models")
        try:
            assert started.wait(5)
            assert pool.submit(client.get, "/api/health").result(timeout=1).json() == {"status": "ok"}
            assert not pending.done()
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert response.status_code == 200, response.text
    assert any(row["ref"] == "llamacpp:local" for row in response.json()) is answers


def test_provider_list_leaves_health_available_during_settings_read(isolated_settings, monkeypatch):
    started, release = Event(), Event()
    original = providers.load_settings

    def delayed_read():
        started.set()
        assert release.wait(5)
        return original()

    monkeypatch.setattr(providers, "load_settings", delayed_read)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.get, "/api/providers")
        try:
            assert started.wait(5)
            assert pool.submit(client.get, "/api/health").result(timeout=1).json() == {"status": "ok"}
            assert not pending.done()
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert response.status_code == 200
    assert {row["preset"]["kind"] for row in response.json()} == {kind.value for kind in ProviderKind}


def test_provider_save_waits_for_real_settings_lock_without_blocking_health(isolated_settings, monkeypatch):
    started = Event()
    original = providers.update_provider

    def observed_update(*args, **kwargs):
        started.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(providers, "update_provider", observed_update)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        with providers._SETTINGS_LOCK:
            pending = pool.submit(client.put, "/api/providers/custom", json={"enabled": True, "api_base": "http://model-box/v1"})
            assert started.wait(5)
            assert pool.submit(client.get, "/api/health").result(timeout=1).json() == {"status": "ok"}
            assert not pending.done()
        response = pending.result(timeout=5)
    assert response.status_code == 200, response.text
    assert response.json()["api_base"] == "http://model-box/v1"
    saved = providers.load_settings()[ProviderKind.CUSTOM]
    assert saved.enabled and saved.api_base == "http://model-box/v1"


def test_unknown_provider_still_returns_not_found(isolated_settings):
    response = TestClient(app).put("/api/providers/unknown", json={"enabled": True})
    assert response.status_code == 404 and response.json()["detail"] == "unknown provider: unknown"


def test_local_start_keeps_health_available_while_saving_the_choice(isolated_settings, monkeypatch):
    manager = local_vlm.manager()
    started, release = Event(), Event()
    original = manager.choose
    starts = []

    def delayed_choice(use):
        started.set()
        assert release.wait(5)
        original(use)

    def start():
        starts.append(manager.chosen())
        return manager.status()

    monkeypatch.setattr(manager, 'choose', delayed_choice)
    monkeypatch.setattr(manager, 'start', start)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.post, '/api/system/local-model/start')
        try:
            assert started.wait(5)
            assert pool.submit(client.get, '/api/health').result(timeout=1).json() == {'status': 'ok'}
            assert not pending.done()
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert response.status_code == 200 and starts == [True]
