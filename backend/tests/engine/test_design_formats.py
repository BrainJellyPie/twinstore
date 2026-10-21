"""Design-led formats remain valid with customized dining and retail patterns."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("template,theme,grid,tables,categories", [
    ("nordic_lifestyle", "nordic", (22, 18), 0, {"home_design", "books", "flowers", "souvenirs"}),
    ("retro_diner", "retro", (20, 16), 6, {"burger_menu", "restaurant_menu", "cafe_menu", "scoop_menu"}),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_design_defaults_are_furnished_and_currency_safe(template, theme, grid, tables, categories, currency):
    store = generate_store(template, currency=currency)
    assert store.design_theme == theme
    assert store.grid_size == grid
    assert len(store.counters) == 2
    assert sum(rack.type == "table" for rack in store.racks) == tables
    assert categories <= {rack.rack_desc for rack in store.product_racks}
    assert validate(store) == []
    assert store == generate_store(template, currency=currency)


@pytest.mark.parametrize("template", ["nordic_lifestyle", "retro_diner"])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("dimensions", [(8, 6), (40, 40)])
def test_design_formats_accept_other_patterns_and_size_boundaries(template, style, rotation, dimensions):
    options = LayoutOptions(width=dimensions[0], height=dimensions[1], style=style, dining_tables=0,
                            table_rotation=rotation, dining_seats=6, checkouts=1, design_theme="retro" if template == "nordic_lifestyle" else "nordic",
                            products_per_category=1, gate_wall="back", exit_wall="left", exit_position="center")
    store = generate_store(template, options=options)
    assert validate(store) == []
    assert store.product_racks
    assert store.design_theme == options.design_theme
    assert not any(rack.type == "table" for rack in store.racks)
    for category in {rack.rack_desc for rack in store.product_racks}:
        assert len({item.sku for rack in store.product_racks if rack.rack_desc == category for slot in rack.slots for item in slot.items}) == 1
