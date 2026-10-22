"""Provider-free boundaries for generated store settings and optimization constraints."""
import itertools
import math

import pytest

from store_emulator.domain.store import Store
from store_emulator.engine.generators.store_setup_writer import _Setup, to_setup
from store_emulator.engine.optimize.goal import _Goal, to_goal


def store() -> Store:
    return Store(id="fixture", name="Fixture", type="convenience", grid_size=(10, 10), racks=[])


@pytest.mark.parametrize("percent", [0, 100, 2, 0.1, 0.01, 0.005, 0.004, 0.0001, 0.00001, 1e-12, 1e-100, 1e-300])
def test_requested_minimum_gain_is_not_rounded_to_a_different_threshold(percent: float) -> None:
    result = to_goal(_Goal(min_improvement_percent=percent), store())
    assert result.min_improvement is not None
    assert result.min_improvement * 100 == pytest.approx(percent, rel=1e-12, abs=0)
    assert not result.warnings


def test_unrepresentable_positive_gain_is_reported_instead_of_becoming_zero() -> None:
    result = to_goal(_Goal(min_improvement_percent=math.ulp(0.0)), store())
    assert result.min_improvement is None
    assert result.warnings


@pytest.mark.parametrize("percent", [-1, -math.ulp(0.0), 100.0000001, 1e308, math.inf, -math.inf, math.nan])
def test_invalid_minimum_gain_cannot_escape_into_optimizer_settings(percent: float) -> None:
    result = to_goal(_Goal(min_improvement_percent=percent), store())
    assert result.min_improvement is None
    assert result.warnings


@pytest.mark.parametrize("moves", [None, -100, -1, 0, 1, 2, 49, 50, 51, 10**100])
def test_move_limits_keep_the_accepted_endpoints(moves: int | None) -> None:
    result = to_goal(_Goal(max_moves=moves), store())
    valid = moves is not None and 1 <= moves <= 50
    assert result.max_moves == (moves if valid else None)
    assert bool(result.warnings) == (moves is not None and not valid)


@pytest.mark.parametrize("opening,closing", itertools.product([None, -1, *range(25), 25], repeat=2))
def test_opening_window_keeps_only_complete_same_day_pairs(opening: int | None, closing: int | None) -> None:
    result = to_setup(_Setup(open_hour=opening, close_hour=closing), [])
    valid = opening is not None and closing is not None and opening in range(24) and closing in range(opening + 1, 25)
    assert (result.open_hour, result.close_hour) == ((opening, closing) if valid else (None, None))
    assert bool(result.warnings) == (not valid and (opening is not None or closing is not None))


def test_unspecified_opening_days_do_not_claim_every_day() -> None:
    result = to_setup(_Setup(name="Tea store"), [])
    assert result.open_days is None


@pytest.mark.parametrize("days", ["7", "weekday", "weekend"])
def test_explicit_opening_days_are_retained(days: str) -> None:
    result = to_setup(_Setup.model_validate({"open_days": days}), [])
    assert result.open_days == days


@pytest.mark.parametrize("asked", ["Corner store", "CORNER STORE", "a Corner store format"])
@pytest.mark.parametrize("reverse", [False, True])
def test_colliding_format_names_do_not_pick_the_first_catalog_entry(asked: str, reverse: bool) -> None:
    formats = [("one", "Corner store", "convenience"), ("two", "corner store", "grocery")]
    result = to_setup(_Setup(format=asked), list(reversed(formats)) if reverse else formats)
    assert result.template_id == ""
    assert result.store_type == ""
    assert result.warnings


def test_repeated_alias_for_the_same_format_still_resolves() -> None:
    result = to_setup(_Setup(format="Corner store"), [("same", "Corner store", "convenience")] * 2)
    assert result.template_id == "same"
    assert not result.warnings


@pytest.mark.parametrize("asked", ["Tea", "Steak", "Unknown", "Tea and Steak"])
def test_format_names_use_whole_names_and_reject_equally_plausible_matches(asked: str) -> None:
    result = to_setup(_Setup(format=asked), [("tea", "Tea", "convenience"), ("steak", "Steak", "grocery")])
    # The longest whole name is used; an unrelated substring must not match Tea.
    expected = {"Tea": "tea", "Steak": "steak", "Unknown": "", "Tea and Steak": "steak"}[asked]
    assert result.template_id == expected
