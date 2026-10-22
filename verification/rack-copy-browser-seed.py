"""Run with the backend Python in a fresh, disposable working directory."""
from pathlib import Path
import io
from PIL import Image
from store_emulator.application.storage.seed import seed_sample_projects
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, setup_path
from store_emulator.application.storage.images import save_image
from store_emulator.application.setups import set_active_setup
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store

if Path(".data").exists():
    raise SystemExit("Use a fresh directory; existing data is preserved.")
seed_sample_projects()
pid, sid = "proj_67916afd", "setup_copy_fixture"
photo = io.BytesIO(); Image.new("RGB", (16, 16), "blue").save(photo, format="PNG")
save_image(pid, "tea", photo.getvalue(), "synthetic.png")
store = Store(id="copy_fixture", name="Shelf reuse fixture", type="convenience", currency="USD", grid_size=(12, 12), racks=[
    Rack(id="in", type="entrance", shape=[[1]], position=(0, 11)),
    Rack(id="out", type="exit", shape=[[1]], position=(11, 11)),
    Rack(id="source", rack_name="Reviewed tea shelf", type="shelf", shape=[[1]], position=(2, 2), slots=[
        Slot(block=0, face="S", level=1, items=[SlotItem(sku="tea", name="Tea", price=231, regular_price=299, promo="Local"), SlotItem(sku="sample", name="Sample", price=0)]),
        Slot(block=0, face="W", level=4, items=[SlotItem(sku="other", name="Other", price=999)])]),
    Rack(id="empty", rack_name="Empty shelf", type="shelf", shape=[[1]], position=(5, 2)),
    Rack(id="empty2", rack_name="Second empty shelf", type="shelf", shape=[[1]], position=(8, 2)),
    Rack(id="fridge", type="fridge", shape=[[1]], position=(2, 6)),
])
source = new_setup_data("Shelf reuse fixture", None, store.model_dump(mode="json")); source["id"] = sid
write_json(setup_path(pid, sid), source)
set_active_setup(pid, sid)
print("Seeded synthetic shelves/products/image, no model calls or actual store data.")
