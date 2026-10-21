"""Keep user-designated floor space open without losing access to stocked fixtures."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("template_id", ["community_pharmacy", "family_restaurant"])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("origin", [(1, 1), (5, 4), (14, 10)])
def test_reserved_floor_space_stays_empty_and_shopping_routes_stay_connected(template_id, style, origin):
    area = ReservedArea(label="Consultation corner", x=origin[0], y=origin[1], width=5, height=5)
    options = LayoutOptions(width=20, height=16, style=style, density="dense", checkouts=4,
                            entrance="center", reserved_areas=[area])
    store = generate_store(template_id, seed=11, options=options)
    clear = {(x, y) for x in range(area.x, area.x + area.width) for y in range(area.y, area.y + area.height)}
    occupied = {pos for rack in store.racks for pos in rack.occupied_positions}
    assert clear.isdisjoint(occupied)
    assert all(store.walkable_grid()[y][x] == 1 for x, y in clear)
    assert store.product_racks and len(store.counters) == 4
    assert validate(store) == []
    assert store == generate_store(template_id, seed=11, options=options)


def test_reservation_checks_the_whole_table_and_recomputes_available_capacity():
    # Only the table's bottom-right cell is reserved; checking just its anchor would miss it.
    area = ReservedArea(label="Pickup", x=3, y=3, width=1, height=1)
    small = generate_store("book_cafe", options=LayoutOptions(width=8, height=6, reserved_areas=[area]))
    assert not any(r.type == "table" for r in small.racks)
    assert validate(small) == []
    with pytest.raises(ValueError, match="at most 0 dining tables"):
        generate_store("book_cafe", options=LayoutOptions(width=8, height=6, dining_tables=1, reserved_areas=[area]))


def test_overlapping_reservations_are_combined_without_blocking_walking():
    areas = [ReservedArea(label="Events", x=2, y=2, width=5, height=4),
             ReservedArea(label="Pickup", x=4, y=3, width=4, height=3)]
    store = generate_store("hypermarket", options=LayoutOptions(reserved_areas=areas))
    occupied = {pos for rack in store.racks for pos in rack.occupied_positions}
    for area in areas:
        assert all((x, y) not in occupied for x in range(area.x, area.x + area.width)
                   for y in range(area.y, area.y + area.height))
    assert validate(store) == []


def test_a_reservation_must_fit_the_selected_format_or_custom_dimensions():
    area = ReservedArea(label="Large event space", x=10, y=8, width=5, height=4)
    with pytest.raises(ValueError, match="must fit inside"):
        generate_store("compact_cvs", options=LayoutOptions(reserved_areas=[area]))
    assert validate(generate_store("compact_cvs", options=LayoutOptions(width=20, height=16, reserved_areas=[area]))) == []
