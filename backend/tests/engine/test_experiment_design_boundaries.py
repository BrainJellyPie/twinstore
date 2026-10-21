"""Drafted tests must satisfy the same naming and price contract as manually entered tests."""
from decimal import Decimal, ROUND_HALF_UP
import pytest
from store_emulator.domain.marketing import ExperimentRequest
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.marketing.experiment_design import _Draft, to_design

@pytest.fixture
def store():
    return Store(id='s', name='Store', type='convenience', grid_size=(8,8), racks=[
        Rack(id='r', rack_name='Drinks', type='shelf', shape=[[1]], position=(3,3), slots=[
            Slot(block=0, face='N', level=1, items=[SlotItem(sku='tea',name='Tea',price=199)])])])

def design(store, variants, currency='USD'):
    return to_design(_Draft.model_validate({'name':'Test','variants':variants}), store, currency, [])

def promo(name):
    return {'name':name, 'changes':[{'kind':'promo','product':'Tea','promo':'SALE'}]}

@pytest.mark.parametrize('names', [
    ['X'*40]*5,
    ['Special', 'Special (4)', 'Special', 'special', 'SPECIAL'],
    ['Control', 'Control (2)', 'CONTROL', 'control (4)', 'Control'],
    ['𠮷'*40]*5,
    ['x'*39, 'x'*39],
])
def test_duplicate_names_remain_unique_after_suffixing_and_truncation(store, names):
    result = design(store, [promo(n) for n in names])
    request = ExperimentRequest(setup_id='setup', variants=result.variants, focus_skus=result.focus_skus, panel=20)
    assert len(request.variants) == len(names)
    assert len({v.name.casefold() for v in request.variants}) == len(names)

@pytest.mark.parametrize('currency,price', [
    ('USD',1.005),('USD',1.025),('USD',1.045),('USD',2.675),
    ('EUR',.005),('EUR',10.125),('KRW',1500.5),('JPY',.5),('JPY',2.5),('VND',100.5),
])
def test_prices_use_the_same_decimal_half_up_rounding_as_the_editor(store,currency,price):
    result = design(store,[{'name':'Price','changes':[{'kind':'price','product':'Tea','price':price}]}],currency)
    divisor=1 if currency in {'KRW','JPY','VND'} else 100
    expected=int((Decimal(str(price))*divisor).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    assert result.variants[0].changes[0].price == expected

@pytest.mark.parametrize('currency,price', [
    ('USD',.004),('USD',5e-324),('JPY',.49),('USD',float('inf')),('USD',float('nan')),('USD',1e308),
])
def test_unrepresentable_prices_are_reported_without_losing_other_valid_changes(store,currency,price):
    result = design(store,[{'name':'Mixed','changes':[
        {'kind':'price','product':'Tea','price':price}, {'kind':'promo','product':'Tea','promo':'SALE'},
    ]}],currency)
    assert [c.kind for c in result.variants[0].changes] == ['promo']
    assert result.warnings

@pytest.mark.parametrize('target', ['product', 'shelf', 'package'])
@pytest.mark.parametrize('same_identity', [False, True])
def test_names_only_resolve_when_the_matching_identity_is_unique(store,target,same_identity):
    from copy import deepcopy
    rack=store.racks[0]
    rack.slots[0].items.append(SlotItem(sku='water',name='Water',price=100))
    packages=[]
    if target=='product':
        rack.slots[0].items.append(SlotItem(sku='tea' if same_identity else 'other_tea',name='TEA',price=299))
        change={'kind':'price','product':'Tea','price':1.50}
    elif target=='shelf':
        other=deepcopy(rack);other.id='r' if same_identity else 'other_rack';other.rack_name='DRINKS';store.racks.append(other)
        change={'kind':'move','product':'Tea','shelf':'Drinks','level':3}
    else:
        packages=[('New pack','asset_1'),('NEW PACK','asset_1' if same_identity else 'asset_2')]
        change={'kind':'package','product':'Tea','package':'New pack'}
    draft=_Draft.model_validate({'name':'Test','focus_products':['Tea'],'variants':[{'name':'Mixed','changes':[change,{'kind':'promo','product':'Water','promo':'SALE'}]}]})
    result=to_design(draft,store,'USD',packages)
    assert [c.kind for c in result.variants[0].changes] == ([change['kind'],'promo'] if same_identity else ['promo'])
    if not same_identity:
        assert result.warnings
        if target=='product':assert result.focus_skus==['water']
