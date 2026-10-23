"""A photo-chart run keeps one coherent shelf photograph and product-box mapping."""

import base64
import io
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from store_emulator.application import shelf_views, simulation
from store_emulator.application.product_images import snapshot_image_loader
from store_emulator.application.storage.images import save_image
from store_emulator.application.storage.setups import metadata_path, read_setup
from store_emulator.domain.config import EngineType
from store_emulator.engine.perception.shelf_photo import load_shelf_photo
from tests.server.test_marketing_image_snapshot import pixels, picture
from tests.server.test_simulation_image_snapshot import art, running, layout
from tests.server.test_simulation_setup_races import PID, SID

URL = f"/api/projects/{PID}/setups/{SID}/shelf-views"


def upload(client, face, color):
    stream = io.BytesIO()
    Image.new("RGB", (100, 140), color).save(stream, "PNG")
    boxes = {f"{face['face']}:1:0:0": [[10, 20, 50, 90]] if color == "red" else [[40, 60, 90, 130]]}
    return client.put(f"{URL}/{face['key']}", json={
        "rack_id": face["rack_id"], "face": face["face"], "boxes": boxes,
        "image": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode(),
    })


def signature(photo):
    return (pixels(photo.image), photo.boxes) if photo else None


def start(client, preview=False):
    return client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": SID, "engine_type": "vlm_glance", "shelf_view": "photo_chart", "preview": preview,
        "run_id": "run_photo",
    })


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("when", ["queued", "running"])
def test_photo_chart_uses_accepted_photo_and_boxes(running, monkeypatch, present, preview, when):
    client, submit = running
    face = client.get(URL).json()["faces"][0]
    if present:
        assert upload(client, face, "red").status_code == 200
    expected = signature(load_shelf_photo(str(shelf_views.views_dir(PID)), face["key"]))
    original = simulation.run_simulation
    seen = []

    async def run(config, store, people, **kwargs):
        if when == "running":
            assert upload(client, face, "blue").status_code == 200
        seen.append(signature(load_shelf_photo(config.engines.vlm_glance.shelf_views_dir, face["key"])))
        return await original(config.model_copy(update={"engine_type": EngineType.RULE_BASED}), store, people, **kwargs)

    monkeypatch.setattr(simulation, "run_simulation", run)
    response = start(client, preview)
    assert response.status_code == 200, response.text
    if when == "queued":
        assert upload(client, face, "blue").status_code == 200
    job, *args = submit.call_args.args
    job(*args, **submit.call_args.kwargs)
    status = simulation.get_run_status(PID, "run_photo")
    assert status["status"] == "completed", status["error"]
    assert seen == [expected]


@pytest.mark.parametrize("other", ["upload", "delete_project", "start_run"])
def test_photo_and_boxes_commit_together_before_another_writer_or_deletion(running, monkeypatch, other):
    client, _ = running
    face = client.get(URL).json()["faces"][0]
    ready, release = Event(), Event()
    original = Path.write_bytes
    paused = False

    def write(path, content):
        nonlocal paused
        result = original(path, content)
        if path == shelf_views.views_dir(PID) / f"{face['key']}.jpg" and not paused:
            paused = True
            ready.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(Path, "write_bytes", write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(upload, client, face, "red")
        try:
            assert ready.wait(5)
            if other == "upload":
                second = pool.submit(upload, client, face, "blue")
            elif other == "start_run":
                second = pool.submit(start, client)
            else:
                second = pool.submit(client.delete, f"/api/projects/{PID}")
            with pytest.raises(TimeoutError):
                second.result(timeout=.1)
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200
        assert second.result(timeout=5).status_code == 200
    if other == "delete_project":
        assert not metadata_path(PID).parent.exists()
    elif other == "upload":
        photo = load_shelf_photo(str(shelf_views.views_dir(PID)), face["key"])
        assert photo is not None
        assert photo.image.getpixel((50, 50))[2] > 240
        assert list(photo.boxes.values()) == [((40.0, 60.0, 90.0, 130.0),)]
    else:
        folder = metadata_path(PID).parent / "runs/run_photo/input/shelf_views"
        photo = load_shelf_photo(str(folder.resolve()), face["key"])
        assert photo is not None and photo.image.getpixel((50, 50))[0] > 240
        assert list(photo.boxes.values()) == [((10.0, 20.0, 50.0, 90.0),)]


def test_sku_replacement_cannot_split_layout_photo_keys_from_captured_product_art(running, monkeypatch):
    client, submit = running
    target, expected_art, _ = art("sku")
    face = client.get(URL).json()["faces"][0]
    assert upload(client, face, "red").status_code == 200
    expected_photo = signature(load_shelf_photo(str(shelf_views.views_dir(PID)), face["key"]))
    ready, release = Event(), Event()
    original = simulation._load_simulation_inputs

    def load(*args):
        result = original(*args)
        ready.set()
        assert release.wait(5)
        return result

    monkeypatch.setattr(simulation, "_load_simulation_inputs", load)
    with ThreadPoolExecutor(max_workers=2) as pool:
        starting = pool.submit(start, client)
        try:
            assert ready.wait(5)
            changing = pool.submit(save_image, PID, target.sku, picture("blue"), "blue.png")
            with pytest.raises(TimeoutError):
                changing.result(timeout=.1)
        finally:
            release.set()
        response = starting.result(timeout=5)
        changing.result(timeout=5)
    assert response.status_code == 200, response.text
    accepted_store = submit.call_args.args[4]
    accepted = next(i for r in accepted_store.racks for s in r.slots for i in s.items if i.sku == target.sku)
    folder = metadata_path(PID).parent / "runs/run_photo/input"
    assert pixels(snapshot_image_loader(folder / "images")(accepted)) == expected_art
    assert signature(load_shelf_photo(str(folder / "shelf_views"), face["key"])) == expected_photo


def test_photo_copy_failure_does_not_publish_a_pending_run(running, monkeypatch):
    client, submit = running
    face = client.get(URL).json()["faces"][0]
    assert upload(client, face, "red").status_code == 200
    original = shelf_views.shutil.copyfile

    def copy(source, target, **kwargs):
        if "/runs/" in str(target) and str(target).endswith(".json"):
            raise OSError("photo metadata copy failed")
        return original(source, target, **kwargs)

    monkeypatch.setattr(shelf_views.shutil, "copyfile", copy)
    assert start(client).status_code == 500
    submit.assert_not_called()
    assert not (metadata_path(PID).parent / "runs/run_photo").exists()
    assert read_setup(PID, SID)["status"] == "draft"
    assert load_shelf_photo(str(shelf_views.views_dir(PID)), face["key"]) is not None


def test_lost_photo_snapshot_does_not_use_current_project_photos(running, monkeypatch):
    client, submit = running
    face = client.get(URL).json()["faces"][0]
    assert upload(client, face, "red").status_code == 200
    assert start(client).status_code == 200
    folder = metadata_path(PID).parent / "runs/run_photo/input/shelf_views"
    (folder / "manifest.json").unlink()
    assert upload(client, face, "blue").status_code == 200
    run = AsyncMock()
    monkeypatch.setattr(simulation, "run_simulation", run)
    job, *args = submit.call_args.args
    job(*args, **submit.call_args.kwargs)
    assert simulation.get_run_status(PID, "run_photo")["status"] == "failed"
    assert read_setup(PID, SID)["status"] == "draft"
    run.assert_not_called()


@pytest.mark.parametrize("missing", ["jpg", "json"])
def test_incomplete_photo_pair_stays_absent_after_a_later_upload(running, missing):
    client, _ = running
    face = client.get(URL).json()["faces"][0]
    assert upload(client, face, "red").status_code == 200
    (shelf_views.views_dir(PID) / f"{face['key']}.{missing}").unlink()
    assert start(client).status_code == 200
    assert upload(client, face, "blue").status_code == 200
    folder = metadata_path(PID).parent / "runs/run_photo/input/shelf_views"
    assert load_shelf_photo(str(folder.resolve()), face["key"]) is None
