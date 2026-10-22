"""Run after library-photos-browser-seed.py in the same disposable verification directory."""
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.rack import Rack
from store_emulator.domain.store import Store

pid, sid = "proj_67916afd", "setup_copy_i18n"
if setup_path(pid, sid).exists():
    raise SystemExit("The fixture already exists; preserve it rather than overwriting.")
original = read_setup(pid, "setup_photos_fixture")
store = Store.model_validate(original["store"])
store.racks.append(Rack(id="empty", rack_name="Empty shelf", type="shelf", shape=[[1]], position=(5, 2)))
draft = new_setup_data("Rack copy i18n fixture", None, store.model_dump(mode="json"))
draft["id"] = sid
write_json(setup_path(pid, sid), draft)
print("Seeded a synthetic stocked shelf and an empty destination; the previous fixture is unchanged.")
