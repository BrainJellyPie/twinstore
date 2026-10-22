"""Drafts must resolve prices and image identities without changing their meaning."""
import pytest
from store_emulator.engine.marketing.survey_design import _Draft, to_design


@pytest.mark.parametrize('currency,price,expected', [
    ('USD', 1.005, 101), ('USD', 1.015, 102), ('EUR', 2.675, 268),
    ('GBP', 0.005, 1), ('USD', 0.0049, None), ('USD', 5e-324, None),
    *[(currency, 2.5, 3) for currency in ('KRW', 'JPY', 'VND', 'CLP', 'ISK', 'HUF', 'TWD', 'IDR')],
    ('KRW', .4999, None), ('JPY', .5, 1), ('usd', 1.005, 101),
    ('USD', float('inf'), None), ('USD', 1e308, None), ('JPY', 1e308, None),
    ('USD', 90071992547409.92, None), ('JPY', 9007199254740992.0, None),
    ('JPY', 9007199254740991.0, 9007199254740991), ('USD', 0, None), ('USD', None, None),
])
def test_reference_prices_round_half_up_and_stay_representable(currency, price, expected):
    draft = _Draft(name='Price test', questions=['value'], reference_price=price)
    result = to_design(draft, [], currency)
    assert result.reference_price == expected
    assert result.currency == currency.upper()
    if price and expected is None:
        assert any('price' in warning.lower() for warning in result.warnings)


@pytest.mark.parametrize('asked,packages,expected', [
    ('Unknown', [('', 'empty')], []),
    ('', [('', 'empty'), ('Gold', 'gold')], []),
    ('Gold', [(' Gold ', 'a'), ('gold', 'b')], []),
    ('"Gold", brand Tea Co', [('Gold', 'a'), ('GOLD', 'b')], []),
    ('Gold Leaf', [('Gold', 'gold'), ('Leaf', 'leaf')], []),
    ('Steak', [('Tea', 'tea')], []),
    ('Gold', [('Gold', 'a'), ('Gold', 'a')], ['a']),
    ('"Label Leaf", brand Tea Co', [('Label Leaf', 'leaf')], ['leaf']),
    ('Gold Extra', [('Gold', 'a'), ('Gold Extra', 'b')], ['b']),
    ('Gold Extra, brand Co', [('Gold', 'a'), ('Gold Extra', 'b')], ['b']),
    ('새 포장', [('새 포장', 'ko')], ['ko']),
    ('新しい茶', [('新しい茶', 'ja')], ['ja']),
    ('🛒', [('🛒', 'cart')], ['cart']),
])
@pytest.mark.parametrize('reverse', [False, True])
def test_only_unambiguous_library_images_are_selected(asked, packages, expected, reverse):
    draft = _Draft(name='Image test', images=[asked], questions=['preference'])
    result = to_design(draft, list(reversed(packages)) if reverse else packages, 'USD')
    assert result.stimuli == expected
    assert 'preference' not in result.questions
    if not expected:
        assert result.warnings
