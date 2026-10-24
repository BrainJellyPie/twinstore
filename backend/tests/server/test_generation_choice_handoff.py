"""A late confirmation response must not revive a canceled or finished generation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import generation_async as ga
from store_emulator.application.storage.generations import init_generation, read_status, write_status
from store_emulator.server.main import app

PID, SID = "proj_choice", "setup_choice"


@pytest.fixture
def waiting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = init_generation(PID, SID, "persona")
    write_status(PID, gid, "running", progress={"confirm": {
        "all": {"customers": 1000}, "sample": {"customers": 100},
    }})
    return gid, TestClient(app)


@pytest.mark.parametrize("choice,terminal", [
    ("all", "completed"), ("sample", "completed"),
    ("all", "failed"), ("sample", "failed"), ("cancel", "failed"),
])
def test_worker_terminal_status_survives_a_slow_confirmation_write(waiting, monkeypatch, choice, terminal):
    gid, client = waiting
    ready, release, finished = Event(), Event(), Event()
    original_write = ga.write_status

    def paused_status(*args, **kwargs):
        ready.set()
        assert release.wait(5)
        original_write(*args, **kwargs)

    monkeypatch.setattr(ga, "write_status", paused_status)
    # The accepted answer can still be committing when the six-hour deadline
    # arrives. Speed up that boundary without changing the actual polling loop.
    monkeypatch.setattr(ga, "CHOICE_WAIT_SEC", 0.1)

    def worker():
        selected = asyncio.run(asyncio.wait_for(ga._await_choice(PID, gid), timeout=3))
        write_status(PID, gid, terminal, error="Canceled" if choice == "cancel" else "",
                     progress={"count": 100 if terminal == "completed" else 0})
        finished.set()
        return selected

    with ThreadPoolExecutor(max_workers=2) as pool:
        answering = pool.submit(client.post, f"/api/projects/{PID}/setups/{SID}/generations/{gid}/confirm",
                                json={"choice": choice})
        try:
            assert ready.wait(5)
            consuming = pool.submit(worker)
            finished.wait(0.2)
        finally:
            release.set()
        response = answering.result(timeout=5)
        assert consuming.result(timeout=5) == choice
    assert response.status_code == 200, response.text
    saved = read_status(PID, gid)
    assert saved["status"] == terminal
    assert saved["progress"] == {"count": 100 if terminal == "completed" else 0}
    assert saved["error"] == ("Canceled" if choice == "cancel" else "")


@pytest.mark.parametrize("first_choice", ["all", "sample", "cancel"])
@pytest.mark.parametrize("second_choice", ["all", "sample", "cancel"])
def test_overlapping_answers_cannot_replace_an_accepted_choice(waiting, monkeypatch, first_choice, second_choice):
    gid, client = waiting
    ready, release = Event(), Event()
    original_write = ga.write_status

    def paused_choice(*args, **kwargs):
        if not ready.is_set():
            ready.set()
            assert release.wait(5)
        original_write(*args, **kwargs)

    monkeypatch.setattr(ga, "write_status", paused_choice)
    url = f"/api/projects/{PID}/setups/{SID}/generations/{gid}/confirm"
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, url, json={"choice": first_choice})
        try:
            assert ready.wait(5)
            second = pool.submit(client.post, url, json={"choice": second_choice})
            try:
                second.result(timeout=0.2)
            except TimeoutError:
                pass
        finally:
            release.set()
        accepted, rejected = first.result(timeout=5), second.result(timeout=5)
    assert accepted.status_code == 200, accepted.text
    assert rejected.status_code == 409, rejected.text
    assert asyncio.run(asyncio.wait_for(ga._await_choice(PID, gid), timeout=1)) == first_choice


@pytest.mark.parametrize("choice", ["all", "sample", "cancel"])
def test_failed_status_write_keeps_the_confirmation_retryable(waiting, monkeypatch, choice):
    gid, _ = waiting
    original_write = ga.write_status

    def fail_choice(*args, **kwargs):
        raise OSError("Offline storage failure")

    monkeypatch.setattr(ga, "write_status", fail_choice)
    with pytest.raises(OSError, match="Offline storage failure"):
        ga.choose_write_size(PID, SID, gid, choice)
    assert "confirm" in read_status(PID, gid)["progress"]
    monkeypatch.setattr(ga, "write_status", original_write)
    ga.choose_write_size(PID, SID, gid, choice)
    assert asyncio.run(asyncio.wait_for(ga._await_choice(PID, gid), timeout=1)) == choice


@pytest.mark.parametrize("same_job", [False, True])
def test_busy_choice_is_retryable_and_does_not_block_other_jobs(waiting, monkeypatch, same_job):
    gid, client = waiting
    monkeypatch.setattr(ga, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    before = read_status(PID, gid)
    with FileLock(ga._choice_lock_path(PID, gid if same_job else "gen_other"), timeout=0):
        response = client.post(f"/api/projects/{PID}/setups/{SID}/generations/{gid}/confirm", json={"choice": "cancel"})
    assert response.status_code == (503 if same_job else 200), response.text
    if same_job:
        assert read_status(PID, gid) == before
    else:
        assert asyncio.run(asyncio.wait_for(ga._await_choice(PID, gid), timeout=1)) == "cancel"


def test_missing_generation_does_not_create_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))
    response = TestClient(app).post(f"/api/projects/{PID}/setups/{SID}/generations/gen_missing/confirm",
                                    json={"choice": "sample"})
    assert response.status_code == 404, response.text
    assert set(tmp_path.rglob("*")) == before


def test_expired_wait_closes_confirmation_before_the_worker_finalizes(waiting, monkeypatch):
    gid, client = waiting
    monkeypatch.setattr(ga, "CHOICE_WAIT_SEC", 0)
    with pytest.raises(ValueError, match="Nobody chose"):
        asyncio.run(ga._await_choice(PID, gid))
    response = client.post(f"/api/projects/{PID}/setups/{SID}/generations/{gid}/confirm", json={"choice": "all"})
    assert response.status_code == 409, response.text
