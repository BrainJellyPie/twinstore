"""Drafted studies preserve price meaning and cannot silently lose their price axis."""

import pytest

from store_emulator.domain.marketing import ConjointRequest
from store_emulator.engine.marketing.conjoint_design import _Draft, to_design


def draft(prices, attributes=2):
    return _Draft(name="Price study", product="Tea", prices=prices,
        attributes=[{"name": "Style", "levels": ["Regular", "Zero"]},
                    {"name": "Pack", "levels": ["Can", "Bottle"]}][:attributes])


@pytest.mark.parametrize("currency, prices, expected", [
    ("USD", [1.005, 1.015], [101, 102]),
    ("EUR", [2.675, 3.005], [268, 301]),
    ("GBP", [.005, .015], [1, 2]),
    ("usd", [1.004, 1.005], [100, 101]),
    *[(currency, [2.49, 2.5], [2, 3]) for currency in ("KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR")],
    ("USD", [0, 1.49], [0, 149]),
    ("JPY", [0, 1], [0, 1]),
])
def test_price_levels_round_half_up_and_preserve_explicit_free_options(currency, prices, expected):
    source = draft(prices, attributes=1)
    before = source.model_dump()
    result = to_design(source, currency, [])
    assert result.prices == expected
    ConjointRequest.model_validate(result.model_dump())
    assert source.model_dump() == before


@pytest.mark.parametrize("currency, prices", [
    ("USD", [.0049, 1]), ("JPY", [.4999, 1]),
    ("USD", [float("inf"), 1]), ("USD", [float("nan"), 1, 2]),
    ("USD", [1e308, 1]), ("JPY", [1e308, 1]),
    ("USD", [90071992547409.92, 1]), ("JPY", [9007199254740992.0, 1]),
])
def test_invalid_prices_reject_the_draft_instead_of_changing_the_study(currency, prices):
    with pytest.raises(ValueError, match="price|Price"):
        to_design(draft(prices), currency, [])


@pytest.mark.parametrize("prices", [[1], [1, 1], [1.001, 1.002], [0, 0]])
def test_collapsed_prices_cannot_silently_become_a_study_without_price(prices):
    with pytest.raises(ValueError, match="price|Price"):
        to_design(draft(prices), "USD", [])


def test_no_price_is_valid_when_the_model_explicitly_drafts_two_other_attributes():
    result = to_design(draft([]), "USD", [])
    assert result.prices == []
    ConjointRequest.model_validate(result.model_dump())


def test_legacy_negative_candidates_are_ignored_when_a_valid_price_axis_remains():
    result = to_design(draft([-1, 1, 2]), "USD", [])
    assert result.prices == [100, 200]


def test_one_attribute_without_price_is_not_returned_as_a_usable_design():
    with pytest.raises(ValueError, match="at least two attributes"):
        to_design(draft([], attributes=1), "USD", [])
