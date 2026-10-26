"""Layout problems name racks as the floor editor shows them."""

from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


def test_an_overlap_names_both_racks_by_their_shown_names():
    store = generate_store(TEMPLATES[0].id)
    a, b = [r for r in store.racks if r.type not in ("entrance", "exit") and r.rack_name][:2]
    a.position = b.position
    messages = [i.message for i in validate(store) if i.code == "overlap"]
    assert messages and any(a.rack_name in m and b.rack_name in m for m in messages)
    assert not any(f"'{a.id}'" in m for m in messages)
