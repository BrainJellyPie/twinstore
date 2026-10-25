"""Photo crops must be readable under the SKU actually placed in the saved layout."""

import io

import pytest
from PIL import Image

from store_emulator.application.product_images import project_image_loader
from store_emulator.application.storage import images
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import read_setup, setup_path
from store_emulator.domain.capture import Box, CaptureItem, CaptureResult
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen import generate_store
from tests.server.test_shelf_lab_start_snapshot import CID, lab
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("new_rack", [False, True])
@pytest.mark.parametrize("separate_metadata", [False, True])
@pytest.mark.parametrize("existing_image", [False, True])
def test_applied_exact_match_saves_photo_under_placed_sku(lab, new_rack, separate_metadata, existing_image):
    client, _, _, folder = lab
    store = generate_store("mini_mart")
    rack = next(r for r in store.product_racks if r.slots)
    original_sku = rack.slots[0].items[0].sku
    name = "TwinStore Original Cola 500ml"
    for _, slot in store.all_slots:
        for item in slot.items:
            if item.sku == original_sku:
                item.sku, item.name, item.image_url = "stored_bottle", name, None
    data = read_setup(PID, SID)
    write_json(setup_path(PID, SID), {**data, "store": store.model_dump(mode="json")})
    captured = CaptureResult(image_size=(160, 160), currency="USD", items=[
        CaptureItem(id="i1", band=0, level=1, order=0, sku="cap_read", labeled=True, price=399,
                    name="Original Cola" if separate_metadata else name,
                    brand="TwinStore" if separate_metadata else "", size="500ml" if separate_metadata else "",
                    boxes=[Box(x1=10, y1=10, x2=70, y2=150)]),
        CaptureItem(id="i2", band=0, level=1, order=1, sku="cap_new", labeled=True, price=299,
                    name="Unlisted Mango Bottle", boxes=[Box(x1=90, y1=10, x2=150, y2=150)]),
    ])
    write_json(folder / "result.json", captured.model_dump(mode="json"))
    with Image.new("RGB", (160, 160), "red") as photo:
        photo.paste((0, 255, 0), (80, 0, 160, 160))
        photo.save(folder / "image.jpg")
    if existing_image:
        buffer = io.BytesIO()
        with Image.new("RGB", (30, 40), "blue") as picture:
            picture.save(buffer, "PNG")
        images.save_image(PID, "stored_bottle", buffer.getvalue(), "existing.png")
    source_before = setup_path(PID, SID).read_bytes()
    capture_before = (folder / "result.json").read_bytes()
    original_entry = images.load_manifest(PID).get("stored_bottle")
    saved_manifest = None
    for _ in range(2):
        response = client.post(f"/api/projects/{PID}/captures/{CID}/apply", json={
            "setup_id": SID, "rack_id": rack.id, "face": rack.slots[0].face.value, "new_rack": new_rack,
        })
        assert response.status_code == 200, response.text
        body = response.json()
        child = Store.model_validate(read_setup(PID, body["setup_id"])["store"])
        placed = {item.sku: item for saved in child.racks if saved.id in body["rack_ids"]
                  for slot in saved.slots for item in slot.items}
        assert {"stored_bottle", "cap_new"} <= set(placed) and "cap_read" not in placed
        manifest = images.load_manifest(PID)
        assert set(manifest) == {"stored_bottle", "cap_new"}
        if existing_image:
            assert manifest["stored_bottle"] == original_entry
        if saved_manifest is not None:
            assert manifest == saved_manifest
        saved_manifest = manifest
        loader = project_image_loader(PID)
        for sku, channel in (("stored_bottle", 2 if existing_image else 0), ("cap_new", 1)):
            picture = loader(placed[sku])
            assert picture is not None
            pixel = picture.convert("RGB").getpixel((picture.width // 2, picture.height // 2))
            assert pixel[channel] > 240 and sum(pixel) - pixel[channel] < 30
            fetched = client.get(f"/api/projects/{PID}/images", params={"sku": sku})
            assert fetched.status_code == 200
        assert setup_path(PID, SID).read_bytes() == source_before
        assert (folder / "result.json").read_bytes() == capture_before
