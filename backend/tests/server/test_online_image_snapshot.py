"""Online input and historical replays keep artwork accepted at run start."""

from unittest.mock import Mock

import pytest
from PIL import Image

from store_emulator.application import online, shelf_lab
from store_emulator.application.storage.images import save_image
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.engine.files import remove_tree
from tests.server.test_marketing_image_snapshot import picture, pixels
from tests.server.test_online_api import PID, client


@pytest.fixture
def queued(client, monkeypatch):
    submit = Mock()
    monkeypatch.setattr(online.executor, "submit", submit)
    monkeypatch.setattr(online, "tries_rival", lambda *args: True)
    return client, submit


def stores(client, source):
    sites, products, changes = [], [], []
    for index in range(3):
        base = f"/api/projects/{PID}/online/sites"
        site = client.post(base, json={"template_id": "pet_store"}).json()
        product = {**site["products"][0], "sku": f"frozen_{index}", "image_url": ""}
        if source == "package":
            asset = shelf_lab.upload_package(PID, picture("red"), "red.png", remove_background=False)
            product["image_url"] = shelf_lab.package_path(PID, asset.asset_id).resolve().as_uri()
            changes.append(lambda aid=asset.asset_id: shelf_lab.delete_package(PID, aid))
        else:
            if source == "sku":
                save_image(PID, product["sku"], picture("red"), "red.png")
            changes.append(lambda sku=product["sku"]: save_image(PID, sku, picture("blue"), "blue.png"))
        site.update(products=[product], options={**site["options"], "welcome_popup": "none", "cookie_banner": False,
                                               "cart_reminder": False})
        response = client.put(f"{base}/{site['id']}", json=site)
        assert response.status_code == 200, response.text
        sites.append(response.json())
        products.append(online.get_site(PID, site["id"]).products[0])
    expected = [pixels(online._picture(PID)(product)) for product in products]
    return sites, products, expected, lambda: [change() for change in changes]


def start(client, sites):
    response = client.post(f"/api/projects/{PID}/online/runs", json={
        "site_ids": [s["id"] for s in sites[:2]], "rival_site_id": sites[2]["id"],
        "shoppers": 1, "max_steps": 3, "seed": 3, "mobile_share": 0,
        "missions": {"purchase": 1}, "arrivals": {"search_engine": 1},
    })
    assert response.status_code == 200, response.text
    return response.json()["run_id"]


def work(submit):
    function, *args = submit.call_args.args
    function(*args, **submit.call_args.kwargs)


@pytest.mark.parametrize("source", ["sku", "added", "package"])
@pytest.mark.parametrize("when", ["queued", "running"])
def test_worker_uses_accepted_art_for_variants_and_rival(queued, monkeypatch, source, when):
    client, submit = queued
    sites, products, expected, change = stores(client, source)
    original = online._simulate
    seen = []

    async def simulate(sites, shoppers, policy, request, picture, progress, rival=None):
        if when == "running":
            change()
        seen.extend(pixels(picture(product)) for product in products)
        return await original(sites, shoppers, policy, request, picture, progress, rival)

    monkeypatch.setattr(online, "_simulate", simulate)
    rid = start(client, sites)
    if when == "queued":
        change()
    work(submit)
    assert online.get_run(PID, rid).status.status == "completed"
    assert seen == expected


@pytest.mark.parametrize("source", ["sku", "added", "package"])
def test_replay_screenshots_metadata_and_gif_use_accepted_art(queued, monkeypatch, source):
    client, submit = queued
    sites, _, expected, change = stores(client, source)
    rid = start(client, sites)
    work(submit)
    assert online.get_run(PID, rid).status.status == "completed"
    before = [online.step_screenshot(PID, rid, variant, "os0001", 0, highlight=False) for variant in range(3)]
    change()
    seen = []
    original = online._shot

    def shot(site, shopper, step, picture):
        seen.append(pixels(picture(site.products[0])))
        return original(site, shopper, step, picture)

    monkeypatch.setattr(online, "_shot", shot)
    for variant in range(3):
        assert online.step_screenshot(PID, rid, variant, "os0001", 0, highlight=False) == before[variant]
        online.step_screenshot(PID, rid, variant, "os0001", 0)
        online.playback(PID, rid, variant, "os0001")
        online.journey_gif(PID, rid, variant, "os0001")
    assert seen and all(value == expected[0] for value in seen)


def test_snapshot_write_failure_leaves_no_queued_or_pending_run(queued, monkeypatch):
    client, submit = queued
    sites, _, _, _ = stores(client, "sku")
    save = Image.Image.save

    def fail(self, path, *args, **kwargs):
        if "/online/runs/" in str(path) and "/images/" in str(path):
            raise OSError("snapshot disk full")
        return save(self, path, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError, match="snapshot disk full"):
        start(client, sites)
    submit.assert_not_called()
    assert not list((online._root(PID) / "runs").iterdir())


@pytest.mark.parametrize("missing", ["manifest", "folder"])
def test_lost_snapshot_does_not_show_changed_project_images(queued, missing):
    client, submit = queued
    sites, _, _, change = stores(client, "sku")
    rid = start(client, sites)
    work(submit)
    folder = online._run_dir(PID, rid) / "images"
    if missing == "folder":
        if folder.exists():
            remove_tree(folder)
    else:
        (folder / "manifest.json").unlink(missing_ok=True)
    change()
    with pytest.raises(online.AppError, match="saved product images") as error:
        online.step_screenshot(PID, rid, 0, "os0001", 0)
    assert error.value.status_code == 404


def test_legacy_run_without_snapshot_marker_can_still_replay(queued):
    client, submit = queued
    sites, _, _, _ = stores(client, "sku")
    rid = start(client, sites)
    work(submit)
    folder = online._run_dir(PID, rid)
    data = read_json(folder / "status.json")
    data.pop("image_snapshot", None)
    write_json(folder / "status.json", data)
    if (folder / "images").exists():
        remove_tree(folder / "images")
    assert online.step_screenshot(PID, rid, 0, "os0001", 0).startswith(b"\x89PNG")
