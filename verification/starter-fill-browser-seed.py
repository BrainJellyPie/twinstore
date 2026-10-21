"""Seed only a fresh disposable directory, using the backend environment."""
import io
from pathlib import Path
from PIL import Image
from store_emulator.application.storage.seed import seed_sample_projects
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, setup_path
from store_emulator.application.storage.images import save_image
from store_emulator.application.setups import set_active_setup
from store_emulator.domain.rack import BlockFace, Rack, Slot
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item

if Path(".data").exists():
    raise SystemExit("Use a fresh directory; existing data is preserved.")
seed_sample_projects()
pid, sid = "proj_67916afd", "setup_starter_fixture"
water = catalog_slot_item(CATALOG["water_sports"][0], "USD")
water.name, water.price, water.promo = "My water", 231, "Local"
store = Store(id="starter_fixture", name="Empty shelves fixture", type="convenience", currency="USD", grid_size=(8, 8), racks=[
    Rack(id="in", type="entrance", shape=[[1]], position=(0, 7)),
    Rack(id="out", type="exit", shape=[[1]], position=(7, 7)),
    Rack(id="counter", type="counter", shape=[[1]], position=(7, 0)),
    Rack(id="empty", rack_name="Empty shelf", rack_desc="water_sports", type="shelf", shape=[[1]], position=(3, 3), locked_faces=[BlockFace(block=0, face="N")]),
    Rack(id="stocked", rack_name="Keep these products", type="shelf", shape=[[1]], position=(4, 3), slots=[Slot(block=0, face="S", level=1, items=[water])]),
    Rack(id="fridge", rack_name="Empty fridge", type="fridge", shape=[[1]], position=(2, 0)),
])
source = new_setup_data("Starter fill fixture", None, store.model_dump(mode="json")); source["id"] = sid
write_json(setup_path(pid, sid), source)
set_active_setup(pid, sid)
photo = io.BytesIO(); Image.new("RGB", (16, 16), "blue").save(photo, format="PNG")
save_image(pid, water.sku, photo.getvalue(), "synthetic.png")
write_json(Path("fixture.json"), {"sku": water.sku})
print("Seeded two empty racks, one existing product and a synthetic image. No actual stock or model data.")
