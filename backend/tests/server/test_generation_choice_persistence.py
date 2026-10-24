"""Rejected confirmation requests must not start customer-writing work."""

import asyncio

import pytest

from store_emulator.application import generation_async as ga
from store_emulator.application.storage import io as storage_io
from store_emulator.application.storage.generations import read_status
from tests.server.test_generation_choice_handoff import PID, SID, waiting  # noqa: F401


@pytest.mark.parametrize("choice", ["all", "sample", "cancel"])
def test_failed_confirmation_status_cannot_be_consumed(waiting, monkeypatch, choice):
    gid, _ = waiting
    before = read_status(PID, gid)
    original = ga.write_status

    def fail_status(*args, **kwargs):
        raise OSError("Offline confirmation status failure")

    monkeypatch.setattr(ga, "write_status", fail_status)
    with pytest.raises(OSError, match="Offline confirmation status failure"):
        ga.choose_write_size(PID, SID, gid, choice)
    assert read_status(PID, gid) == before
    monkeypatch.setattr(ga, "write_status", original)
    monkeypatch.setattr(ga, "CHOICE_WAIT_SEC", 0)
    with pytest.raises(ValueError, match="Nobody chose"):
        asyncio.run(ga._await_choice(PID, gid))


@pytest.mark.parametrize("stage", ["fsync", "replace"])
@pytest.mark.parametrize("choice", ["all", "sample", "cancel"])
@pytest.mark.parametrize("retry", ["all", "sample", "cancel"])
def test_failed_atomic_commit_waits_for_the_successful_retry(waiting, monkeypatch, stage, choice, retry):
    gid, _ = waiting
    before = read_status(PID, gid)

    def fail(*args, **kwargs):
        raise OSError("Offline atomic commit failure")

    with monkeypatch.context() as failure:
        if stage == "fsync":
            failure.setattr(storage_io.os, "fsync", fail)
        else:
            failure.setattr(storage_io, "replace_file", fail)
        with pytest.raises(OSError, match="Offline atomic commit failure"):
            ga.choose_write_size(PID, SID, gid, choice)
    assert read_status(PID, gid) == before
    retried = False

    async def retry_when_worker_waits(_seconds):
        nonlocal retried
        assert not retried
        retried = True
        ga.choose_write_size(PID, SID, gid, retry)

    monkeypatch.setattr(ga.asyncio, "sleep", retry_when_worker_waits)
    assert asyncio.run(asyncio.wait_for(ga._await_choice(PID, gid), timeout=1)) == retry
    assert retried
    progress = read_status(PID, gid)["progress"]
    assert "confirm" not in progress
    if retry != "cancel":
        assert progress["total"] == (1000 if retry == "all" else 100)


def test_uncommitted_legacy_choice_is_not_accepted(waiting, monkeypatch):
    gid, _ = waiting
    storage_io.write_json(ga.generation_dir(PID, gid) / "choice.json", {"choice": "all"})
    monkeypatch.setattr(ga, "CHOICE_WAIT_SEC", 0)
    with pytest.raises(ValueError, match="Nobody chose"):
        asyncio.run(ga._await_choice(PID, gid))
