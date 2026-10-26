"""Country-qualified dollars must not silently use another dollar currency."""
import pytest

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.engine.capture.catalog_match import price_minor_units

ALIASES = [('US', 'USD'), ('CA', 'CAD'), ('AU', 'AUD'), ('NZ', 'NZD'), ('HK', 'HKD'), ('SG', 'SGD'), ('NT', 'TWD')]


@pytest.mark.parametrize('prefix,source,currency', [(prefix, source, currency) for prefix, source in ALIASES for _, currency in ALIASES if currency != source])
@pytest.mark.parametrize('guess', [None, 1, 100])
def test_qualified_foreign_currency_cannot_be_overridden_by_a_numeric_guess(prefix, source, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=f'{prefix}$1.00', price=guess), currency, 249) is None


@pytest.mark.parametrize('prefix,currency', ALIASES)
@pytest.mark.parametrize('template', ['{}$1.00', '{} $1.00', '{}$0.00'])
def test_matching_qualified_dollars_remain_literal_prices(prefix, currency, template):
    printed = template.format(prefix.lower())
    expected = 0 if '0.00' in printed else 1 if currency == 'TWD' else 100
    assert price_minor_units(ShelfItemLabel(price_text=printed, price=99), currency, 249) == expected


@pytest.mark.parametrize('prefix,currency', ALIASES)
@pytest.mark.parametrize('template', ['SAVE {}$1.00', 'FROM {}$1.00', 'DEPOSIT {}$1.00', '{}$1.00 OFF', '{}$1.00 / L', '-{}$1.00', '−{}$1.00'])
def test_qualified_units_do_not_hide_non_selling_or_negative_price_context(prefix, currency, template):
    assert price_minor_units(ShelfItemLabel(price_text=template.format(prefix), price=1), currency, 249) is None


@pytest.mark.parametrize('printed,currency,expected', [
    ('ＣＡ＄１．００', 'USD', None), ('ＣＡ＄１．００', 'CAD', 100),
    ('HK$1.00 USD', 'USD', None), ('US$1.00 CAD', 'CAD', None),
    ('FOCUS$1.00', 'USD', 100), ('MAC$1.00', 'USD', 100),
    ('US$1.00 WITH COUPON', 'USD', 100), ('$1.00', 'CAD', 100),
    ('CA$', 'USD', None),
])
def test_qualified_unit_boundaries_and_shared_symbols(printed, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=printed, price=1), currency, 249) == expected
