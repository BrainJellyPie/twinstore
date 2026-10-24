"""Neighborhood comparisons keep accepted artwork through edits and cache eviction."""

from functools import lru_cache
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import product_images, projects, town_synergy
from store_emulator.application.storage.images import save_image
from store_emulator.application.storage.setups import metadata_path, read_setup
from store_emulator.domain.rack import SlotItem
from store_emulator.server.main import app
from tests.server.test_simulation_image_snapshot import art, pixels
from tests.server.test_marketing_image_snapshot import picture
from tests.server.test_simulation_setup_races import PID, SID, layout
from tests.server.test_study_queue_failure import studies


@pytest.mark.parametrize("source", ["package", "sku", "added"])
@pytest.mark.parametrize("when", ["queued", "running", "between_arms"])
def test_synergy_keeps_accepted_art(studies, monkeypatch, source, when):
    client, requests = studies
    _, endpoint, body = requests["synergy"]
    pool = Mock()
    monkeypatch.setattr(town_synergy, "executor", pool)
    monkeypatch.setattr(town_synergy, "build_client", lambda *args: object())
    target, expected, mutate = art(source)
    saved = read_setup(PID, SID)
    other = SlotItem.model_validate(next(i for r in saved["store"]["racks"] for s in r["slots"]
        for i in s["items"] if i["sku"] != target.sku))
    save_image(PID, other.sku, picture("green"), "green.png")
    monkeypatch.setattr(product_images, "lru_cache", lambda *, maxsize: lru_cache(maxsize=1))
    seen = []

    async def compare(town, venue_id, store, personas, **kwargs):
        loader = kwargs["engine"]._image_loader
        loader(SlotItem(sku="another_shelf", name="Other", price=100))
        if when == "running":
            mutate()
        accepted = next(i for r in store.racks for s in r.slots for i in s.items if i.sku == target.sku)
        seen.append(pixels(loader(accepted)))
        if when == "between_arms":
            mutate()
            # A one-image cache exercises ordinary eviction with a small fixture.
            assert loader(other) is not None
        seen.append(pixels(loader(accepted)))
        raise ValueError("Offline probe finished after reading both arms")

    monkeypatch.setattr(town_synergy, "vlm_basket_synergy", compare)
    response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert response.status_code == 200, response.text
    if when == "queued":
        mutate()
    function, *args = pool.submit.call_args.args
    function(*args, **pool.submit.call_args.kwargs)
    assert seen == [expected, expected]
    folder = town_synergy._dir(PID, response.json()["job_id"])
    assert (folder / "images/manifest.json").is_file()
    assert town_synergy.get_synergy_job(PID, response.json()["job_id"]).status.status == "failed"


@pytest.mark.parametrize("stage", ["image", "manifest", "status"])
def test_failed_snapshot_registration_cleans_up_without_queuing(studies, monkeypatch, stage):
    _, requests = studies
    _, endpoint, body = requests["synergy"]
    client = TestClient(app, raise_server_exceptions=False)
    art("sku")
    pool = Mock()
    monkeypatch.setattr(town_synergy, "executor", pool)
    save = Image.Image.save
    from store_emulator.application.storage import io as storage_io
    replace = storage_io.replace_file

    def fail_image(self, path, *args, **kwargs):
        if stage == "image" and "/synergy/" in str(path) and "/images/" in str(path):
            raise OSError("Offline image save failure")
        return save(self, path, *args, **kwargs)

    def fail_commit(source, destination):
        if "/synergy/" in str(destination) and destination.name == stage + ".json":
            raise OSError("Offline snapshot registration failure")
        return replace(source, destination)

    monkeypatch.setattr(Image.Image, "save", fail_image)
    monkeypatch.setattr(storage_io, "replace_file", fail_commit)
    response = client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    assert response.status_code == 500, response.text
    pool.submit.assert_not_called()
    assert not list((metadata_path(PID).parent / "synergy").glob("*"))
    projects.delete_project(PID)
    assert not metadata_path(PID).parent.exists()
