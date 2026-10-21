"""A shelf target must still match products stocked on other shelves too."""
import pytest

from store_emulator.domain.scenario import Scenario
from store_emulator.engine.layout_gen.templates import generate_store
from store_emulator.engine.scenario import apply_to_store
from store_emulator.engine.scenario_writer import ScenarioDraft, matched_skus, to_scenario


@pytest.mark.parametrize('template', ['urban_cvs', 'pet_superstore', 'sports_outlet'])
@pytest.mark.parametrize('copies', [1, 3])
@pytest.mark.parametrize('target', ['Target shelf', 'TARGET SHELF'])
def test_shelf_targets_match_shared_products_without_changing_other_shelves(template, copies, target):
    store = generate_store(template, seed=1)
    rack = next(r for r in store.product_racks if r.slots)
    target_rack = rack.model_copy(deep=True, update={'id': 'target', 'rack_name': 'Target shelf'})
    others = [rack.model_copy(deep=True, update={'id': f'other_{i}', 'rack_name': f'Other shelf {i}'}) for i in range(copies)]
    store = store.model_copy(update={'racks': [target_rack, *others]})
    original = store.model_dump(mode='json')
    expected = {item.sku for slot in target_rack.slots for item in slot.items}
    assert expected
    assert matched_skus(store, target) == expected
    draft = ScenarioDraft.model_validate({'name': 'Shelf offer', 'promotions': [{'target': target}], 'stockouts': [target]})
    described = to_scenario(draft, 'An offer and stock-out on the target shelf.', store)
    assert [p.target for p in described.scenario.promotions] == [target]
    assert described.scenario.stockouts == [target]
    assert not any('No product' in warning for warning in described.warnings)
    after, _ = apply_to_store(store, Scenario(stockouts=described.scenario.stockouts))
    assert sum(len(slot.items) for slot in after.racks[0].slots) == 0
    assert after.racks[1:] == others
    assert store.model_dump(mode='json') == original


def test_a_missing_target_is_still_dropped_with_a_warning():
    store = generate_store('urban_cvs', seed=1)
    target = 'Nonexistent target XYZ'
    assert matched_skus(store, target) == set()
    described = to_scenario(ScenarioDraft.model_validate({'name': 'Missing', 'promotions': [{'target': target}], 'stockouts': [target]}), 'Missing shelf', store)
    assert described.scenario.promotions == [] and described.scenario.stockouts == []
    assert len(described.warnings) == 2 and all('No product' in warning for warning in described.warnings)
