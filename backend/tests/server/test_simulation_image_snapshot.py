"""A vision run keeps the artwork accepted with its layout, including missing art."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import shelf_lab, simulation
from store_emulator.application.product_images import project_image_loader
from store_emulator.application.storage.images import save_image
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, read_setup, setup_path
from store_emulator.domain.config import EngineType
from store_emulator.domain.rack import SlotItem
from store_emulator.engine.files import remove_tree
from store_emulator.server.main import app
from store_emulator.server.routes import simulate
from tests.server.test_marketing_image_snapshot import picture, pixels
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def running(layout, monkeypatch):
    monkeypatch.setattr(simulate, "ensure_resolvable", lambda config: None)
    submit = Mock()
    monkeypatch.setattr(simulate.executor, "submit", submit)
    return TestClient(app, raise_server_exceptions=False), submit


def art(source):
    saved = read_setup(PID, SID)
    item = next(i for r in saved["store"]["racks"] for s in r["slots"] for i in s["items"])
    item.update(sku="snapshot_target", image_url=None)
    if source == "package":
        package = shelf_lab.upload_package(PID, picture("red"), "red.png", remove_background=False)
        item["image_url"] = shelf_lab.package_path(PID, package.asset_id).resolve().as_uri()
        mutate = lambda: shelf_lab.delete_package(PID, package.asset_id)
    else:
        if source == "sku":
            save_image(PID, item["sku"], picture("red"), "red.png")
        mutate = lambda: save_image(PID, item["sku"], picture("blue"), "blue.png")
    write_json(setup_path(PID, SID), saved)
    target = SlotItem.model_validate(item)
    return target, pixels(project_image_loader(PID)(target)), mutate


@pytest.mark.parametrize("source", ["package", "sku", "added"])
@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("when", ["queued", "running"])
def test_vision_run_uses_accepted_art(running, monkeypatch, source, preview, when):
    client, submit = running
    target, expected, mutate = art(source)
    original = simulation.run_simulation
    seen = []

    async def run(config, store, people, **kwargs):
        loader = kwargs["image_loader"]
        # Another shelf is rendered before this one: this image has not been cached yet.
        loader(SlotItem(sku="another_shelf", name="Other", price=100))
        if when == "running":
            mutate()
        accepted = next(i for r in store.racks for s in r.slots for i in s.items if i.sku == target.sku)
        seen.append(pixels(loader(accepted)))
        return await original(config.model_copy(update={"engine_type": EngineType.RULE_BASED}), store, people, **kwargs)

    monkeypatch.setattr(simulation, "run_simulation", run)
    response = client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": SID, "engine_type": "vlm_glance", "preview": preview, "run_id": "run_art",
    })
    assert response.status_code == 200, response.text
    if when == "queued":
        mutate()
    job, *args = submit.call_args.args
    job(*args, **submit.call_args.kwargs)
    assert simulation.get_run_status(PID, "run_art")["status"] == "completed"
    assert seen == [expected]
    assert (metadata_path(PID).parent / "runs/run_art/input/images/manifest.json").is_file()


@pytest.mark.parametrize("preview", [False, True])
def test_failed_image_snapshot_leaves_no_pending_run_or_locked_layout(running, monkeypatch, preview):
    client, submit = running
    art("sku")
    save = Image.Image.save

    def fail(self, path, *args, **kwargs):
        if "/runs/" in str(path) and "/images/" in str(path):
            raise OSError("snapshot disk full")
        return save(self, path, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail)
    response = client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": SID, "engine_type": "vlm_glance", "preview": preview, "run_id": "run_art",
    })
    assert response.status_code == 500
    submit.assert_not_called()
    assert read_setup(PID, SID)["status"] == "draft"
    assert not (metadata_path(PID).parent / "runs/run_art").exists()


def test_rule_run_does_not_copy_product_images(running):
    client, _ = running
    art("sku")
    response = client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": SID, "engine_type": "rule_based", "run_id": "run_art",
    })
    assert response.status_code == 200, response.text
    assert not (metadata_path(PID).parent / "runs/run_art/input/images").exists()


@pytest.mark.parametrize("missing", ["manifest", "folder"])
def test_lost_snapshot_does_not_fall_back_to_changed_project_art(running, monkeypatch, missing):
    client, submit = running
    _, _, mutate = art("sku")
    response = client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": SID, "engine_type": "vlm_glance", "run_id": "run_art",
    })
    assert response.status_code == 200, response.text
    folder = metadata_path(PID).parent / "runs/run_art/input/images"
    if missing == "manifest":
        (folder / "manifest.json").unlink()
    else:
        remove_tree(folder)
    mutate()
    run = AsyncMock()
    monkeypatch.setattr(simulation, "run_simulation", run)
    job, *args = submit.call_args.args
    job(*args, **submit.call_args.kwargs)
    assert simulation.get_run_status(PID, "run_art")["status"] == "failed"
    assert read_setup(PID, SID)["status"] == "draft"
    run.assert_not_called()
