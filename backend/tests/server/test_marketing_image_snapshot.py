"""An accepted visual study must keep the images it compares while source art changes."""

import hashlib
import io

import pytest
from PIL import Image

from store_emulator.application import marketing, product_images, shelf_lab
from store_emulator.application.storage import images as image_storage
from store_emulator.application.product_images import project_image_loader, snapshot_image_loader, snapshot_project_images
from store_emulator.application.storage.images import save_image
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.rack import SlotItem
from store_emulator.engine.optimize.evaluate import LayoutEvaluator
from tests.server.test_shelf_test_integrity import BODY, PID, SID, client
from tests.server.test_shelf_lab_start_snapshot import overlap


def picture(color):
    out = io.BytesIO()
    Image.new("RGBA", (25, 40), color).save(out, "PNG")
    return out.getvalue()


def pixels(image):
    return (image.size, hashlib.sha256(image.tobytes()).hexdigest()) if image is not None else None


def source_art(source):
    changes = BODY["changes"]
    item = SlotItem(sku="A0017", name="Original", price=100)
    if source == "package":
        asset = shelf_lab.upload_package(PID, picture("red"), "red.png", remove_background=False)
        changes = [{"kind": "package", "sku": item.sku, "asset_id": asset.asset_id}]
        item = item.model_copy(update={"image_url": shelf_lab.package_path(PID, asset.asset_id).resolve().as_uri()})
        mutate = lambda: shelf_lab.delete_package(PID, asset.asset_id)
    else:
        if source == "sku":
            save_image(PID, item.sku, picture("red"), "red.png")
        mutate = lambda: save_image(PID, item.sku, picture("blue"), "blue.png")
    return changes, pixels(project_image_loader(PID)(item)), mutate


@pytest.mark.parametrize("source", ["package", "sku", "added"])
@pytest.mark.parametrize("when", ["queued", "rendering"])
def test_shelf_panel_keeps_accepted_art(client, monkeypatch, source, when):
    changes, expected, mutate = source_art(source)
    seen = []
    original_panel = marketing.shelf_panel

    async def panel(llm, personas, control, test, face, **kwargs):
        item = next(i for s in test.slots for i in s.items if i.sku == "A0017")
        seen.append(pixels(kwargs["image_loader"](item)))
        return await original_panel(llm, personas, control, test, face, **kwargs)

    monkeypatch.setattr(marketing, "shelf_panel", panel)
    started = client.post(f"/api/projects/{PID}/shelf-tests", json={**BODY, "changes": changes})
    assert started.status_code == 200, started.text
    if when == "queued":
        mutate()
    else:
        render = marketing.render_face
        changed = False

        def render_then_change(*args, **kwargs):
            nonlocal changed
            result = render(*args, **kwargs)
            if not changed:
                changed = True
                mutate()
            return result

        monkeypatch.setattr(marketing, "render_face", render_then_change)
    marketing.executor.submit.call_args.args[0]()
    view = client.get(f"/api/projects/{PID}/shelf-tests/{started.json()['job_id']}").json()
    assert view["status"] == "completed", view["error"]
    assert seen == [expected]


@pytest.mark.parametrize("source", ["package", "sku", "added"])
def test_vision_experiment_keeps_accepted_art(client, monkeypatch, source):
    changes, expected, mutate = source_art(source)
    seen = []

    async def evaluate(self, store, people):
        item = next(i for r in store.product_racks for s in r.slots for i in s.items if i.sku == "A0017")
        seen.append(pixels(self._engine._image_loader(item)))
        return [CustomerResult(persona_id=p.id, day=p.day, arrival_time="12:00:00") for p in people]

    monkeypatch.setattr(LayoutEvaluator, "evaluate_customers", evaluate)
    monkeypatch.setattr(marketing, "ensure_resolvable", lambda config: None)
    monkeypatch.setattr(marketing, "build_client", lambda *args: object())
    body = {"setup_id": SID, "engine": "vlm", "model": "openai/gpt-4o-mini", "panel": 20,
            "variants": [{"name": "New art", "changes": changes}]}
    started = client.post(f"/api/projects/{PID}/experiments", json=body)
    assert started.status_code == 200, started.text
    mutate()
    marketing.executor.submit.call_args.args[0]()
    view = client.get(f"/api/projects/{PID}/experiments/{started.json()['job_id']}").json()
    assert view["status"] == "completed", view["error"]
    assert len(seen) == 2
    assert seen[1] == expected


def test_snapshot_survives_cache_eviction_and_keeps_distinct_art_for_one_sku(client, tmp_path):
    root = shelf_lab.package_directory(PID)
    root.mkdir(parents=True, exist_ok=True)
    items = []
    for index in range(131):
        path = root / f"pkg_{index}.png"
        path.write_bytes(picture((index, 0, 0, 255)))
        items.append(SlotItem(sku="same", name="One product", price=100, image_url=path.resolve().as_uri()))
    missing = SlotItem(sku="missing", name="Missing", price=0)
    folder = tmp_path / "snapshots"
    loader = snapshot_project_images(PID, [*items, *items, missing], folder)
    assert len(list(folder.glob("*.png"))) == 131
    for path in root.glob("*.png"):
        path.unlink()
    loader = snapshot_image_loader(folder)
    save_image(PID, missing.sku, picture("blue"), "added.png")
    assert loader(missing) is None
    for index, item in enumerate(items):
        assert loader(item).getpixel((0, 0)) == (index, 0, 0, 255)
    assert loader(items[0]).getpixel((0, 0)) == (0, 0, 0, 255)


@pytest.mark.parametrize("kind", ["shelf", "experiment"])
def test_snapshot_failure_cleans_pending_job_without_submitting(client, monkeypatch, kind):
    changes, _, _ = source_art("package")
    save = Image.Image.save

    def fail_snapshot(self, fp, *args, **kwargs):
        if "/marketing/" in str(fp) and "/images/" in str(fp):
            raise OSError("snapshot disk full")
        return save(self, fp, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail_snapshot)
    monkeypatch.setattr(marketing, "ensure_resolvable", lambda config: None)
    if kind == "shelf":
        endpoint, body = "shelf-tests", {**BODY, "changes": changes}
    else:
        endpoint, body = "experiments", {"setup_id": SID, "engine": "vlm", "panel": 20,
                                         "variants": [{"name": "Pack", "changes": changes}]}
    with pytest.raises(OSError, match="snapshot disk full"):
        client.post(f"/api/projects/{PID}/{endpoint}", json=body)
    marketing.executor.submit.assert_not_called()
    assert marketing.list_jobs(PID, kind) == []


@pytest.mark.parametrize("snapshot_first", [False, True])
def test_snapshot_and_sku_overwrite_keep_one_image_version(client, monkeypatch, tmp_path, snapshot_first):
    item = SlotItem(sku="concurrent", name="Concurrent image", price=100)
    save_image(PID, item.sku, picture("red"), "red.png")

    def snapshot():
        return snapshot_project_images(PID, [item], tmp_path / "study-art")

    def overwrite():
        return save_image(PID, item.sku, picture("blue"), "blue.png")

    if snapshot_first:
        loader, _ = overlap(monkeypatch, product_images, "file_product_image", snapshot, overwrite)
    else:
        _, loader = overlap(monkeypatch, image_storage, "_save_manifest", overwrite, snapshot)
    assert loader(item).getpixel((0, 0)) == ((255, 0, 0, 255) if snapshot_first else (0, 0, 255, 255))
