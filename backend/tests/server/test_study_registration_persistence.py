"""Failed study admission must leave no unqueued jobs or overwritten history."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from store_emulator.application import marketing, projects
from store_emulator.application.storage import io as storage_io
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from tests.server.test_simulation_setup_races import PID, layout
from tests.server.test_study_queue_failure import studies


KINDS = ["experiment", "survey", "shelf", "conjoint", "pitch"]
FAILURES = [(kind, stage) for kind in KINDS for stage in ("request.json", "status.json")]
FAILURES += [("survey", "board.jpg"), ("pitch", "inputs.json")]


@pytest.mark.parametrize("kind,stage", FAILURES)
def test_failed_registration_leaves_no_job_and_can_retry(studies, monkeypatch, kind, stage):
    client, requests = studies
    module, endpoint, body = requests[kind]
    pool = Mock()
    monkeypatch.setattr(module, "executor", pool)
    failed = []
    replace, save = storage_io.replace_file, Image.Image.save

    def replace_file(source, destination):
        if destination.name == stage and not failed:
            failed.append(destination)
            raise OSError("Offline study registration save failure")
        return replace(source, destination)

    def save_image(image, fp, *args, **kwargs):
        if isinstance(fp, Path) and fp.name == stage and not failed:
            failed.append(fp)
            fp.write_bytes(b"partial image")
            raise OSError("Offline partial stimulus image save failure")
        return save(image, fp, *args, **kwargs)

    with monkeypatch.context() as failure:
        failure.setattr(storage_io, "replace_file", replace_file)
        failure.setattr(Image.Image, "save", save_image)
        response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert response.status_code == 500, response.text
    assert len(failed) == 1
    pool.submit.assert_not_called()
    assert not failed[0].parent.exists(), list(failed[0].parent.iterdir())
    assert marketing.list_jobs(PID, kind) == []

    retry = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert retry.status_code == 200, retry.text
    pool.submit.assert_called_once()
    jobs = marketing.list_jobs(PID, kind)
    assert len(jobs) == 1 and jobs[0].status == "pending"
    folder = failed[0].parent.parent / jobs[0].job_id
    assert read_json(folder / "request.json")
    if kind == "survey":
        with Image.open(folder / "board.jpg") as image:
            image.verify()
    if kind == "pitch":
        assert len(read_json(folder / "inputs.json")["personas"]) == 20
    marketing._finish(PID, jobs[0], None, "Offline check finished")
    root = metadata_path(PID).parent
    projects.delete_project(PID)
    assert not root.exists()


@pytest.mark.parametrize("kind", KINDS)
def test_existing_study_directory_is_never_overwritten_or_removed(studies, monkeypatch, kind):
    client, requests = studies
    module, endpoint, body = requests[kind]
    pool = Mock()
    monkeypatch.setattr(module, "executor", pool)
    monkeypatch.setattr(marketing.uuid, "uuid4", lambda: Mock(hex="123456789abc" * 3))
    prefix = {"experiment": "exp", "survey": "srv", "shelf": "slf", "conjoint": "cjt", "pitch": "pit"}[kind]
    folder = marketing._job_dir(PID, kind, f"{prefix}_123456789abc")
    write_json(folder / "request.json", {"previous": "request"})
    (folder / "report.json").write_bytes(b"completed historical report")
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert response.status_code == 409, response.text
    pool.submit.assert_not_called()
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
