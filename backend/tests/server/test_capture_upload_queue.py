"""Upload queue API coverage; real classic detection on generated shelf images, no VLM."""

import io
import time
import pytest
from fastapi.testclient import TestClient
from store_emulator.application import capture
from store_emulator.engine.capture.synthetic import make_scene
from store_emulator.engine.layout_gen.templates import generate_store

PID = "proj_67916afd"
URL = f"/api/projects/{PID}/captures"
FORM = {
    "detector": "classic",
    "model": "none",
    "currency": "USD",
    "rack_type": "shelf",
    "request_id": "a" * 32,
}


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app

    pending = []
    submit = capture.executor.submit

    def track(*args, **kwargs):
        future = submit(*args, **kwargs)
        pending.append(future)
        return future

    monkeypatch.setattr(capture.executor, "submit", track)
    with TestClient(app) as client:
        rack = next(r for r in generate_store("urban_cvs", seed=1).racks if r.slots)
        scene = make_scene(
            rack, rack.slots[0].face, currency="USD", seed=21, severity="mild"
        )
        buffer = io.BytesIO()
        scene.image.save(buffer, format="PNG")
        try:
            yield client, buffer.getvalue(), tmp_path
        finally:
            for future in pending:
                future.result(timeout=30)


def test_same_upload_is_accepted_once_then_recognized(workflow, monkeypatch):
    client, data, _ = workflow
    calls = []
    original = capture.executor.submit

    def submit(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(capture.executor, "submit", submit)
    first = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
    )
    assert first.status_code == 200, first.text
    cid = first.json()["capture_id"]
    retry = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
    )
    assert (
        retry.status_code == 200
        and retry.json()["capture_id"] == cid
        and len(calls) == 1
    )
    for _ in range(200):
        result = client.get(URL + f"/{cid}").json()
        if result["status"]["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)
    assert result["status"]["status"] == "completed", result
    assert result["result"]["items"] and result["result"]["vlm_calls"] == 0


def test_deleted_accepted_photo_is_not_recreated_on_retry(workflow):
    client, data, _ = workflow
    first = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
    )
    cid = first.json()["capture_id"]
    for _ in range(200):
        if client.get(URL + f"/{cid}").json()["status"]["status"] == "completed":
            break
        time.sleep(0.05)
    assert client.delete(URL + f"/{cid}").status_code == 204
    retry = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
    )
    assert retry.status_code == 409 and "removed" in retry.text


def test_rejected_executor_does_not_leave_a_pending_job(workflow, monkeypatch):
    client, data, _ = workflow

    def reject(*args, **kwargs):
        raise RuntimeError("executor stopping")

    monkeypatch.setattr(capture.executor, "submit", reject)
    response = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
    )
    assert response.status_code == 503, response.text
    status = client.get(URL + "/cap_upload_" + "a" * 32).json()["status"]
    assert status["status"] == "failed" and "start" in status["error"]


@pytest.mark.parametrize(
    "request_id", ["a" * 31, "a" * 33, "A" * 32, "../bad", "x" * 1000]
)
def test_invalid_request_identity_is_rejected(workflow, request_id):
    client, data, _ = workflow
    response = client.post(
        URL,
        files={"image": ("Shelf.png", data, "image/png")},
        data={**FORM, "request_id": request_id},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "change", [{"currency": "KRW"}, {"rack_type": "fridge"}, {"model": "different"}]
)
def test_changed_settings_cannot_reuse_a_request(workflow, change):
    client, data, _ = workflow
    assert (
        client.post(
            URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
        ).status_code
        == 200
    )
    response = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data={**FORM, **change}
    )
    assert response.status_code == 409


@pytest.mark.parametrize("data", [b"", b"not an image", b"x" * (25 * 1024 * 1024 + 1)])
def test_invalid_images_do_not_create_jobs(workflow, data, monkeypatch):
    client, _, _ = workflow
    calls = []
    monkeypatch.setattr(capture.executor, "submit", lambda *a, **k: calls.append(a))
    response = client.post(
        URL, files={"image": ("사진.png", data, "image/png")}, data=FORM
    )
    assert response.status_code in (413, 422) and calls == []


def test_concurrent_upload_retries_start_one_job(workflow, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    client, data, _ = workflow
    calls = []
    original = capture.executor.submit

    def submit(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(capture.executor, "submit", submit)

    def post(_):
        return client.post(
            URL, files={"image": ("차 café 🍵.png", data, "image/png")}, data=FORM
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(post, range(2)))
    assert all(r.status_code in (200, 409) for r in responses)
    retry = post(None)
    assert retry.status_code == 200 and len(calls) == 1
    assert retry.json()["image_name"] == "차 café 🍵.png"


def test_restart_marks_abandoned_jobs_failed_and_does_not_restart_a_retry(
    workflow, monkeypatch
):
    client, data, _ = workflow
    calls = []
    monkeypatch.setattr(
        capture.executor, "submit", lambda *args, **kwargs: calls.append(args)
    )
    first = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
    )
    assert first.json()["status"] == "pending"
    assert capture.recover_interrupted_captures() == 1
    assert capture.recover_interrupted_captures() == 0
    retried = client.post(
        URL, files={"image": ("Shelf.png", data, "image/png")}, data=FORM
    )
    assert (
        retried.json()["status"] == "failed"
        and "restart" in retried.json()["error"]
        and len(calls) == 1
    )
