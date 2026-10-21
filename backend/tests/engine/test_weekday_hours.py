"""Explicit weekday schedules are complete, strict, and independent of geometry."""
import pytest
from pydantic import ValidationError
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.domain.types import Weekday
from store_emulator.engine.layout_gen import TEMPLATES, generate_store


def schedule():
    return [{"day": day, "is_open": day not in [3, 7], "open_hour": opening, "close_hour": closing}
            for day, opening, closing in [(1, 0, 1), (2, 23, 24), (3, 9, 18), (4, 0, 24), (5, 9, 17), (6, 10, 14), (7, 9, 18)]]


@pytest.mark.parametrize("template", [template.id for template in TEMPLATES])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_weekday_hours_replace_defaults_without_changing_layout_and_boundaries(template, currency):
    baseline = generate_store(template, currency=currency, seed=3)
    entries = schedule()
    options = LayoutOptions.model_validate({"weekly_hours": list(reversed(entries))})
    store = generate_store(template, currency=currency, seed=3, options=options)
    assert store.model_dump(exclude={"weekly_schedule"}) == baseline.model_dump(exclude={"weekly_schedule"})
    assert [entry.model_dump() for entry in store.weekly_schedule] == entries
    assert [entry.day for entry in options.weekly_hours] == list(range(1, 8))
    assert entries == schedule()
    for entry in entries:
        for hour in range(25):
            assert store.is_open_at(Weekday(entry["day"]), hour) == (entry["is_open"] and entry["open_hour"] <= hour < entry["close_hour"])


@pytest.mark.parametrize("day", range(1, 8))
@pytest.mark.parametrize("hours", [(0, 1), (23, 24), (0, 24)])
def test_single_open_weekday_and_shared_hours_are_restored_when_disabled(day, hours):
    entries = [{"day": d, "is_open": d == day, "open_hour": hours[0], "close_hour": hours[1]} for d in range(1, 8)]
    options = LayoutOptions.model_validate({"weekly_hours": entries, "open_hour": 8, "close_hour": 20, "closed_days": [6, 7]})
    store = generate_store("community_pharmacy", options=options)
    assert [entry.day for entry in store.open_days] == [day]
    restored = generate_store("community_pharmacy", options=options.model_copy(update={"weekly_hours": None}))
    assert [entry.day for entry in restored.open_days] == [1, 2, 3, 4, 5]
    assert {(entry.open_hour, entry.close_hour) for entry in restored.open_days} == {(8, 20)}


@pytest.mark.parametrize("patch", [{"open_hour": 23, "close_hour": 1}, {"closed_days": list(range(1, 8))}, {"closed_days": [1, 1]}, {"close_hour": 8}])
def test_individual_hours_override_unused_shared_hours_even_after_format_change(patch):
    options = LayoutOptions.model_validate({**patch, "weekly_hours": schedule()})
    assert [entry.model_dump() for entry in generate_store("community_pharmacy", options=options).weekly_schedule] == schedule()


@pytest.mark.parametrize("patch", [
    {"day": 0}, {"day": 8}, {"day": True}, {"day": 1.5}, {"day": "1"},
    {"is_open": 1}, {"is_open": "true"}, {"is_open": None}, {"open_hour": -1}, {"open_hour": 24},
    {"open_hour": True}, {"open_hour": 1.5}, {"open_hour": "1"}, {"open_hour": None},
    {"close_hour": 0}, {"close_hour": 25}, {"close_hour": False}, {"close_hour": 1.5}, {"close_hour": "24"},
    {"open_hour": 12, "close_hour": 12}, {"open_hour": 23, "close_hour": 1}, {"timezone": "UTC"},
])
def test_invalid_day_entries_are_rejected(patch):
    entries = schedule(); entries[0].update(patch)
    with pytest.raises(ValidationError):
        LayoutOptions.model_validate({"weekly_hours": entries})


@pytest.mark.parametrize("kind", ["missing", "extra", "duplicate", "closed", "empty", "object", "string"])
def test_reject_incomplete_or_ambiguous_weeks(kind):
    entries = schedule()
    bad = {"missing": entries[:-1], "extra": [*entries, entries[0]], "duplicate": [entries[0], *entries[:-1]],
           "closed": [{**entry, "is_open": False} for entry in entries], "empty": [], "object": {"Monday": entries[0]}, "string": "weekdays"}[kind]
    with pytest.raises(ValidationError):
        LayoutOptions.model_validate({"weekly_hours": bad})


def test_closed_days_can_keep_an_inactive_window_but_reopening_requires_valid_hours():
    entries = schedule(); entries[2].update(open_hour=23, close_hour=1)
    options = LayoutOptions.model_validate({"weekly_hours": entries})
    assert not generate_store("urban_cvs", options=options).is_open_at(Weekday.WED, 23)
    entries[2]["is_open"] = True
    with pytest.raises(ValidationError, match="Closing hour"):
        LayoutOptions.model_validate({"weekly_hours": entries})
