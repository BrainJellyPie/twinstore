"""Run in a fresh disposable directory using the backend Python environment."""
import io
from pathlib import Path
from PIL import Image
from store_emulator.application.storage.seed import seed_sample_projects
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, setup_path
from store_emulator.application.storage.images import save_image
from store_emulator.engine.layout_gen.templates import generate_store

if Path(".data").exists():
    raise SystemExit("Use a fresh fixture directory; existing data is preserved.")
seed_sample_projects()
store = generate_store("urban_cvs", seed=1)
store.currency = "USD"
source = new_setup_data("Bulk edit fixture", None, store.model_dump(mode="json"))
source["id"] = "setup_products_fixture"
write_json(setup_path("proj_67916afd", source["id"]), source)
item = next(item for rack in store.racks for slot in rack.slots for item in slot.items)
photo = io.BytesIO()
Image.new("RGB", (16, 16), "blue").save(photo, format="PNG")
save_image("proj_67916afd", item.sku, photo.getvalue(), "synthetic.png")
write_json(Path("fixture.json"), {"sku": item.sku, "name": item.name})
print("Created template products and a synthetic image; no real prices or model data.")
