"""Create offline browser fixtures in a new, disposable working directory."""

from pathlib import Path

from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.seed import seed_sample_projects
from store_emulator.application.storage.setups import new_setup_data, setup_path
from store_emulator.domain.rack import Rack, RackType
from store_emulator.domain.store import Store
from store_emulator.engine.capture.synthetic import make_scene
from store_emulator.engine.layout_gen.templates import generate_store

if Path(".data").exists():
    raise SystemExit("Choose a new fixture directory; existing .data is preserved.")

seed_sample_projects()
store = Store(
    id="offline", name="Offline queue base", type="convenience", currency="USD",
    grid_size=(14, 14),
    racks=[
        Rack(id="in", type=RackType.ENTRANCE, shape=[[1]], position=(0, 13)),
        Rack(id="out", type=RackType.EXIT, shape=[[1]], position=(13, 13)),
        Rack(id="counter", type=RackType.COUNTER, shape=[[1]], position=(12, 0)),
    ],
)
base = new_setup_data("Queue base", None, store.model_dump(mode="json"))
base["id"] = "setup_queue_base"
write_json(setup_path("proj_67916afd", "setup_queue_base"), base)
rack = next(r for r in generate_store("urban_cvs", seed=1).racks if r.slots)
for i in range(2):
    scene = make_scene(rack, rack.slots[0].face, currency="USD", seed=21 + i, severity="mild")
    scene.image.save(f"photo-{i}.png")
assert Path("photo-0.png").read_bytes() != Path("photo-1.png").read_bytes()
Path("duplicate.png").write_bytes(Path("photo-0.png").read_bytes())
print("Created two synthetic scenes and an identical duplicate; no real store or model data.")
