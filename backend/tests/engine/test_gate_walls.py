"""Generated gates use the requested wall without losing shopping or checkout access."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.id)
@pytest.mark.parametrize("wall,rotation", [("back", 180), ("left", 90), ("right", 270)])
def test_all_formats_support_separate_gates_on_other_walls(template, wall, rotation):
    store = generate_store(template.id, options=LayoutOptions(gate_wall=wall, entrance="left", exit_position="right"))
    width, height = store.grid_size
    expected = {"back": [(1, 0), (width - 2, 0)], "left": [(0, 1), (0, height - 2)], "right": [(width - 1, 1), (width - 1, height - 2)]}[wall]
    assert [store.entrances[0].position, store.exits[0].position] == expected
    assert all(gate.rotation == rotation for gate in store.entrances + store.exits)
    assert len(store.counters) == template.checkouts
    assert validate(store) == []


@pytest.mark.parametrize("gate_wall", ["back", "left", "right"])
@pytest.mark.parametrize("checkout_wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("entrance", ["left", "center", "right"])
@pytest.mark.parametrize("exit_position", ["shared", "center", "right"])
def test_gates_and_counters_never_overlap_on_small_floors(gate_wall, checkout_wall, entrance, exit_position):
    store = generate_store("hypermarket", options=LayoutOptions(
        width=8, height=6, gate_wall=gate_wall, checkout_wall=checkout_wall, checkouts=1,
        entrance=entrance, exit_position=exit_position, density="dense"))
    gates = {gate.position for gate in store.entrances + store.exits}
    assert all(gates.isdisjoint(rack.occupied_positions) for rack in store.racks if rack.type not in ("entrance", "exit"))
    if exit_position == "shared":
        assert store.entrances[0].position == store.exits[0].position
    assert validate(store) == []


@pytest.mark.parametrize("gate_wall", ["back", "left", "right"])
@pytest.mark.parametrize("checkout_wall", ["front", "back", "left", "right"])
def test_checkout_distance_tracks_the_selected_gate_wall(gate_wall, checkout_wall):
    options = LayoutOptions(gate_wall=gate_wall, checkout_wall=checkout_wall, entrance="center", checkouts=2)
    near = generate_store("hypermarket", options=options.model_copy(update={"checkout_placement": "near_entrance"}))
    far = generate_store("hypermarket", options=options.model_copy(update={"checkout_placement": "away_from_entrance"}))
    x, y = near.entrances[0].position
    assert sum(abs(c.position[0] - x) + abs(c.position[1] - y) for c in near.counters) < sum(abs(c.position[0] - x) + abs(c.position[1] - y) for c in far.counters)
    assert validate(near) == validate(far) == []


def test_front_gates_keep_legacy_positions_and_wall_capacity_accounts_for_gates():
    assert generate_store("urban_cvs", seed=3) == generate_store("urban_cvs", seed=3, options=LayoutOptions(gate_wall="front"))
    with pytest.raises(ValueError, match="at most 2 checkout counters on the left wall"):
        generate_store("hypermarket", options=LayoutOptions(width=8, height=6, gate_wall="left", entrance="left", exit_position="right", checkout_wall="left", checkouts=3))


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.id)
@pytest.mark.parametrize("entrance_wall,exit_wall", [("front", "back"), ("back", "front"), ("left", "right"), ("right", "left")])
def test_every_format_supports_opposite_entry_and_exit_walls(template, entrance_wall, exit_wall):
    store = generate_store(template.id, options=LayoutOptions(
        gate_wall=entrance_wall, entrance="center", exit_wall=exit_wall, exit_position="center"))
    width, height = store.grid_size
    positions = {"front": (width // 2, height - 1), "back": (width // 2, 0), "left": (0, height // 2), "right": (width - 1, height // 2)}
    rotations = {"front": 0, "back": 180, "left": 90, "right": 270}
    assert store.entrances[0].position == positions[entrance_wall]
    assert store.exits[0].position == positions[exit_wall]
    assert store.exits[0].rotation == rotations[exit_wall]
    assert len(store.counters) == template.checkouts
    assert validate(store) == []


@pytest.mark.parametrize("entrance_wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("exit_wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("exit_position", ["left", "center", "right"])
def test_small_floor_keeps_independent_exit_and_its_checkout_bank_clear(entrance_wall, exit_wall, exit_position):
    store = generate_store("hypermarket", options=LayoutOptions(
        width=8, height=6, gate_wall=entrance_wall, entrance="center", exit_wall=exit_wall,
        exit_position=exit_position, checkout_wall=exit_wall, checkouts=2, density="dense"))
    gates = {gate.position for gate in store.entrances + store.exits}
    assert all(gates.isdisjoint(rack.occupied_positions) for rack in store.racks if rack.type not in ("entrance", "exit"))
    if entrance_wall != exit_wall:
        assert len(gates) == 2
    assert len(store.counters) == 2
    assert validate(store) == []


@pytest.mark.parametrize("entrance_wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("exit_wall", ["front", "back", "left", "right"])
def test_shared_gate_ignores_a_separate_exit_wall(entrance_wall, exit_wall):
    options = LayoutOptions(gate_wall=entrance_wall, entrance="right")
    default = generate_store("urban_cvs", options=options)
    assert default == generate_store("urban_cvs", options=options.model_copy(update={"exit_wall": exit_wall}))
    assert default == generate_store("urban_cvs", options=options.model_copy(update={"exit_wall": entrance_wall, "exit_position": "right"}))
