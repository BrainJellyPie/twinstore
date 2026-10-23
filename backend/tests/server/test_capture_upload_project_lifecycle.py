"""Photo decoding/acceptance must not recreate a deleted project or lose accepted pending work."""

import io
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import capture, projects
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.setups import metadata_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, layout


@pytest.fixture
def upload(layout, monkeypatch):
    out = io.BytesIO()
    Image.new("RGB", (160, 160), "white").save(out, format="PNG")
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    return TestClient(app), out.getvalue(), submit


def post(client, data, stable):
    form = {"detector": "classic", "model": "none"}
    if stable:
        form["request_id"] = "a" * 32
    return client.post(f"/api/projects/{PID}/captures", files={"image": ("사진.png", data, "image/png")}, data=form)


@pytest.mark.parametrize("stable", [False, True])
@pytest.mark.parametrize("phase", ["prepare_photo", "capture_llm_config"])
def test_project_deleted_during_preparation_is_never_recreated(upload, monkeypatch, stable, phase):
    client, data, submit = upload
    ready, release = Event(), Event()
    original = getattr(capture, phase)

    def paused(*args, **kwargs):
        ready.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(capture, phase, paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(post, client, data, stable)
        try:
            assert ready.wait(5)
            deleted = client.delete(f"/api/projects/{PID}")
            assert deleted.status_code == 200, deleted.text
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert response.status_code == 404, response.text
    submit.assert_not_called()
    assert not metadata_path(PID).parent.exists()
    assert post(client, data, stable).status_code == 404
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("stable", [False, True])
@pytest.mark.parametrize("accept_first", [False, True])
def test_acceptance_and_project_deletion_are_exclusive(upload, monkeypatch, stable, accept_first):
    client, data, submit = upload
    ready, release = Event(), Event()
    module, name = (capture, "_write_status") if accept_first else (projects, "remove_tree")
    original = getattr(module, name)

    def paused(*args, **kwargs):
        ready.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, paused)
    first = lambda: post(client, data, stable)
    second = lambda: client.delete(f"/api/projects/{PID}")
    if not accept_first:
        first, second = second, first
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        try:
            assert ready.wait(5)
            b = pool.submit(second)
            try:
                b.result(timeout=0.2)
            except TimeoutError:
                pass
        finally:
            release.set()
        response, deleted = (a.result(timeout=5), b.result(timeout=5)) if accept_first else (b.result(timeout=5), a.result(timeout=5))
    assert response.status_code == (200 if accept_first else 404), response.text
    assert deleted.status_code == (409 if accept_first else 200), deleted.text
    assert submit.call_count == (1 if accept_first else 0)
    assert metadata_path(PID).parent.exists() is accept_first
