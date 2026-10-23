"""POS product IDs cannot identify a shelf when the same SKU spans rack groups."""

import itertools

import pytest

from store_emulator.engine.analysis.fidelity import PosLine, fidelity_report
from tests.engine.test_shared_store import _shopper, _store


def store_with_shared_sku(*, same_group=False):
    store = _store()
    a = store.product_racks[0]
    a.rack_name = "A"
    b = a.model_copy(deep=True, update={"id": "B", "rack_name": "A" if same_group else "B", "position": (2, 0)})
    for slot in a.slots:
        slot.items = [i for i in slot.items if i.sku != "caviar"]
    for slot in b.slots:
        slot.items = [i for i in slot.items if i.sku != "nuts"]
    store.racks.append(b)
    return store


def report(store, *, real_chips=1, sim_chips=0):
    buys = [("nuts", 1)] + ([("chips", sim_chips)] if sim_chips else [])
    pos = [PosLine(transaction_id="r", sku="nuts", quantity=1, unit_price=350)]
    if real_chips:
        pos.append(PosLine(transaction_id="r", sku="chips", quantity=real_chips, unit_price=300))
    return fidelity_report(store, [_shopper("p", "10:00:00", buys)], pos)


@pytest.mark.parametrize("real_chips,sim_chips", [(1, 0), (0, 1), (1, 1), (-1, 0), (-1, 1)])
@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_sold_shared_skus_do_not_get_assigned_by_rack_order(real_chips, sim_chips, order):
    store = store_with_shared_sku()
    store.racks = [store.racks[i] for i in order]
    result = report(store, real_chips=real_chips, sim_chips=sim_chips)
    scores = {m.name: m.value for m in result.metrics}
    assert scores["rack_spearman"] is None
    assert scores["rack_js_similarity"] is None
    assert scores["sku_spearman"] is not None
    assert scores["basket_value_w1"] is not None
    assert any("multiple rack" in note and "POS" in note for note in result.notes)


@pytest.mark.parametrize("same_group,real_chips,sim_chips", [(True, 1, 1), (False, 0, 0)])
def test_same_category_or_unsold_shared_skus_keep_rack_metrics(same_group, real_chips, sim_chips):
    store = store_with_shared_sku(same_group=same_group)
    for _ in range(2):
        result = report(store, real_chips=real_chips, sim_chips=sim_chips)
        scores = {m.name: m.value for m in result.metrics}
        assert scores["rack_js_similarity"] == 1
        assert scores["rack_spearman"] is not None
        assert not any("multiple rack" in note for note in result.notes)
        store.racks.reverse()


def test_repeated_offers_within_one_rack_remain_unambiguous():
    store = _store()
    rack = store.product_racks[0]
    slot = rack.slots[0]
    rack.slots.append(slot.model_copy(deep=True, update={"level": slot.level + 1}))
    scores = {m.name: m.value for m in report(store, sim_chips=1).metrics}
    assert scores["rack_js_similarity"] == 1
