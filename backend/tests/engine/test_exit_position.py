"""Separate arrival and departure gates stay clear across generated layouts."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("entrance", ["left", "center", "right"])
@pytest.mark.parametrize("exit_position", ["shared", "left", "center", "right"])
@pytest.mark.parametrize("placement", ["auto", "near_entrance", "away_from_entrance"])
@pytest.mark.parametrize("dimensions", [(8, 6), (40, 40)])
def test_gates_are_clear_even_with_four_counters_on_the_smallest_floor(entrance, exit_position, placement, dimensions):
    w, h = dimensions
    options = LayoutOptions(width=w, height=h, entrance=entrance, exit_position=exit_position,
                            checkout_placement=placement, checkouts=4, density="dense", shelf_direction="vertical")
    store = generate_store("hypermarket", options=options)
    positions = {"left": 0, "center": w // 2, "right": w - 1}
    expected_exit = positions[entrance] if exit_position == "shared" else positions[exit_position]
    assert store.entrances[0].position == (positions[entrance], h - 1)
    assert store.exits[0].position == (expected_exit, h - 1)
    gates = {store.entrances[0].position, store.exits[0].position}
    assert all(gates.isdisjoint(r.occupied_positions) for r in store.racks if r.type not in ("entrance", "exit"))
    assert len(store.counters) == 4
    assert validate(store) == []


@pytest.mark.parametrize("template_id", [t.id for t in TEMPLATES])
def test_every_format_supports_separate_gates_with_default_seating(template_id):
    store = generate_store(template_id, options=LayoutOptions(entrance="right", exit_position="center", checkouts=4))
    assert store.entrances[0].position != store.exits[0].position
    assert validate(store) == []


@pytest.mark.parametrize("entrance", ["left", "center", "right"])
def test_legacy_shared_gate_and_explicit_matching_positions_are_identical(entrance):
    legacy = generate_store("urban_cvs", options=LayoutOptions(entrance=entrance))
    assert legacy == generate_store("urban_cvs", options=LayoutOptions(entrance=entrance, exit_position="shared"))
    assert legacy == generate_store("urban_cvs", options=LayoutOptions(entrance=entrance, exit_position=entrance))
