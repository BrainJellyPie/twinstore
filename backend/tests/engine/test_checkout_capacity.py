"""Large checkout banks retain gate and product access, with explicit capacity limits."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("template_id,expected", [
    ("hypermarket", 6), ("warehouse_club", 8), ("food_hall", 4),
    ("organic_market", 2), ("wellness_pharmacy", 2), ("urban_cvs", 1),
])
def test_formats_supply_checkout_defaults_but_preserve_an_explicit_single_counter(template_id, expected):
    store = generate_store(template_id)
    assert len(store.counters) == expected
    assert validate(store) == []
    single = generate_store(template_id, options=LayoutOptions(checkouts=1))
    assert len(single.counters) == 1
    assert validate(single) == []


@pytest.mark.parametrize("count", [8, 12])
@pytest.mark.parametrize("entrance", ["left", "center", "right"])
@pytest.mark.parametrize("exit_position", ["shared", "left", "center", "right"])
@pytest.mark.parametrize("placement", ["auto", "near_entrance", "away_from_entrance"])
def test_large_counter_banks_leave_both_gates_and_stock_accessible(count, entrance, exit_position, placement):
    store = generate_store("food_hall", options=LayoutOptions(width=32, height=26, checkouts=count,
                           entrance=entrance, exit_position=exit_position, checkout_placement=placement,
                           dining_tables=8, table_clearance=2, shelf_direction="vertical"))
    assert len(store.counters) == count
    assert len({r.position for r in store.counters}) == count
    assert validate(store) == []


def test_default_checkout_count_adapts_but_explicit_capacity_is_enforced():
    options = LayoutOptions(width=8, height=6, entrance="center", exit_position="right")
    small = generate_store("warehouse_club", options=options)
    assert len(small.counters) == 4
    assert validate(small) == []
    with pytest.raises(ValueError, match="at most 4 checkout counters"):
        generate_store("warehouse_club", options=options.model_copy(update={"checkouts": 5}))
    near = generate_store("warehouse_club", options=options.model_copy(update={
        "checkouts": 5, "checkout_placement": "near_entrance",
    }))
    assert len(near.counters) == 5 and validate(near) == []
