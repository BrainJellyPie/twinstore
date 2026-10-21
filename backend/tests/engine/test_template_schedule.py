"""Operating hours preserve format defaults and never change floor geometry."""

import pytest
from pydantic import ValidationError

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.id)
@pytest.mark.parametrize("hours,closed", [((0, 24), []), ((6, 15), [6, 7]), ((23, 24), [1, 2, 3, 4, 5, 6])])
def test_every_format_supports_custom_hours_without_moving_stock(template, hours, closed):
    original = generate_store(template.id, seed=13)
    store = generate_store(template.id, seed=13, options=LayoutOptions(
        open_hour=hours[0], close_hour=hours[1], closed_days=closed))
    assert store.racks == original.racks
    assert store.grid_size == original.grid_size
    assert len(store.weekly_schedule) == 7
    assert all((day.open_hour, day.close_hour) == hours for day in store.weekly_schedule)
    assert [int(day.day) for day in store.open_days] == [day for day in range(1, 8) if day not in closed]
    assert generate_store(template.id, seed=13) == original


@pytest.mark.parametrize("hour", range(24))
def test_one_hour_windows_at_each_clock_boundary(hour):
    store = generate_store("station_kiosk", options=LayoutOptions(open_hour=hour, close_hour=hour + 1))
    assert all(day.close_hour - day.open_hour == 1 for day in store.open_days)


@pytest.mark.parametrize("open_day", range(1, 8))
def test_any_weekday_can_be_the_only_open_day(open_day):
    store = generate_store("office_lobby", options=LayoutOptions(closed_days=[d for d in range(1, 8) if d != open_day]))
    assert [int(day.day) for day in store.open_days] == [open_day]


@pytest.mark.parametrize("patch", [
    {"open_hour": -1}, {"open_hour": 24}, {"open_hour": 1.5}, {"open_hour": True},
    {"close_hour": 0}, {"close_hour": 25}, {"close_hour": 2.5}, {"close_hour": False},
    {"open_hour": "9"}, {"close_hour": float("inf")}, {"open_hour": float("nan")},
    {"closed_days": [0]}, {"closed_days": [8]}, {"closed_days": [True]},
    {"closed_days": [1.5]}, {"closed_days": ["1"]}, {"closed_days": list(range(1, 9))},
])
def test_invalid_numeric_and_weekday_values_are_rejected(patch):
    with pytest.raises(ValidationError):
        LayoutOptions.model_validate(patch)


@pytest.mark.parametrize("patch,message", [
    ({"open_hour": 10, "close_hour": 10}, "earlier"),
    ({"open_hour": 22, "close_hour": 6}, "Overnight"),
    ({"open_hour": 22}, "earlier"),  # default closing is 21
    ({"close_hour": 6}, "earlier"),  # default opening is 7
    ({"closed_days": [1, 1]}, "duplicates"),
    ({"closed_days": list(range(1, 8))}, "at least one"),
])
def test_invalid_effective_schedule_is_rejected(patch, message):
    with pytest.raises(ValueError, match=message):
        generate_store("office_lobby", options=LayoutOptions.model_validate(patch))


def test_null_inherits_defaults_while_zero_and_empty_list_override_them():
    default = generate_store("office_lobby")
    inherited = generate_store("office_lobby", options=LayoutOptions(open_hour=None, close_hour=None, closed_days=None))
    assert inherited == default
    assert [int(day.day) for day in default.open_days] == [1, 2, 3, 4, 5]
    all_days = generate_store("office_lobby", options=LayoutOptions(open_hour=0, closed_days=[]))
    assert len(all_days.open_days) == 7
    assert all((day.open_hour, day.close_hour) == (0, 21) for day in all_days.open_days)
