"""A suggested shelf test must preserve prices and target identities."""
import pytest
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.marketing.shelf_test_design import _Draft, to_design
from store_emulator.engine.prompting import resolve_listed


def store():
    return Store(id='s', name='Store', type='convenience', grid_size=(6, 6), currency='USD', racks=[
        Rack(id='tea', type='shelf', shape=[[1]], position=(2, 2), rack_name='Tea shelf',
             slots=[Slot(block=0, face='N', level=1, items=[SlotItem(sku='tea', name='Tea', price=199)])])])


@pytest.mark.parametrize('currency,price,expected', [
    ('USD', 1.005, 101), ('USD', 1.015, 102), ('EUR', 2.675, 268), ('GBP', .005, 1),
    ('USD', .0049, None), ('USD', 5e-324, None), ('KRW', .4999, None), ('JPY', .5, 1),
    *[(c, 2.5, 3) for c in ('KRW', 'JPY', 'VND', 'CLP', 'ISK', 'HUF', 'TWD', 'IDR')],
    ('usd', 1.005, 101), ('USD', float('inf'), None), ('USD', 1e308, None), ('JPY', 1e308, None),
    ('USD', 90071992547409.92, None), ('JPY', 9007199254740992., None),
    ('JPY', 9007199254740991., 9007199254740991), ('USD', 0, 0), ('USD', None, None),
])
def test_shelf_prices_use_half_up_rounding_and_safe_nonnegative_minor_units(currency, price, expected):
    original = store(); before = original.model_dump()
    result = to_design(_Draft(name='Price test', product='Tea', price=price), original, currency, [])
    changes = [c for c in result.changes if c.kind == 'price']
    assert [c.price for c in changes] == ([] if expected is None else [expected])
    if price and expected is None: assert any('price' in warning.lower() for warning in result.warnings)
    assert original.model_dump() == before


@pytest.mark.parametrize('asked,listed,expected', [
    ('Steak', {'tea': {'a'}}, None),
    ('Gold Leaf', {'gold': {'a'}, 'leaf': {'b'}}, None),
    ('Gold Leaf', {'gold': {'a'}, 'leaf': {'a'}}, {'a'}),
    ('"Tea", on Drinks', {'tea': {'a'}}, {'a'}),
    ('Tea Extra ($1.99)', {'tea': {'a'}, 'tea extra': {'b'}}, {'b'}),
    ('Tea', {'tea': {'a', 'b'}}, {'a', 'b'}),
    ('New pack', {'': {'a'}}, None), ('', {'': {'a'}}, None),
    ('새 포장', {'새 포장': {'ko'}}, {'ko'}), ('🛒', {'🛒': {'emoji'}}, {'emoji'}),
])
@pytest.mark.parametrize('reverse', [False, True])
def test_listed_names_do_not_choose_a_target_by_dictionary_order(asked, listed, expected, reverse):
    assert resolve_listed(asked, dict(reversed(list(listed.items()))) if reverse else listed) == expected


@pytest.mark.parametrize('asked', ['Steak', 'Gold Leaf'])
def test_unclear_product_targets_are_refused_before_building_changes(asked):
    original = store(); items = original.racks[0].slots[0].items
    if asked == 'Gold Leaf':
        items[0].name = 'Gold'; items.append(SlotItem(sku='leaf', name='Leaf', price=199))
    with pytest.raises(ValueError): to_design(_Draft(name='Test', product=asked, promo='SALE'), original, 'USD', [])


def test_ambiguous_pack_does_not_change_the_package_but_keeps_an_explicit_sign():
    result = to_design(_Draft(name='Test', product='Tea', package='Gold Leaf', promo='SALE'), store(), 'USD', [('Gold', 'gold'), ('Leaf', 'leaf')])
    assert [c.kind for c in result.changes] == ['promo']
    assert any('Gold Leaf' in warning for warning in result.warnings)
