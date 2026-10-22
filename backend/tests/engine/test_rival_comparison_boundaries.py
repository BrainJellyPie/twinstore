"""Price arithmetic and explicit product identity remain valid at comparison boundaries."""

import math
import pytest
from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.shelf_lab.rival import compare_rival, unmatched_names


def pair(our_name="Tea", rival_name="Tea", our_price=199, rival_price=199):
    store = Store(
        id="s",
        name="Store",
        type="convenience",
        grid_size=(8, 8),
        racks=[
            Rack(
                id="r",
                type="shelf",
                shape=[[1]],
                position=(3, 3),
                slots=[
                    Slot(
                        block=0,
                        face="N",
                        level=1,
                        items=[SlotItem(sku="tea", name=our_name, price=our_price)],
                    )
                ],
            )
        ],
    )
    capture = CaptureResult(
        image_size=(20, 20),
        items=[
            CaptureItem(
                id="i",
                band=0,
                level=1,
                order=0,
                name=rival_name,
                price=rival_price,
                labeled=True,
            )
        ],
    )
    return store, capture


@pytest.mark.parametrize(
    "ours,theirs",
    [
        (20001, 1),
        (1000000, 1),
        (9007199254740991, 1),
        (1, 9007199254740991),
        (199, 1),
        (199, 198),
        (1, 1),
    ],
)
@pytest.mark.parametrize("elasticity", [0.0, 1.0, 3.0])
def test_positive_prices_remain_positive_and_keep_precision_before_logarithms(
    ours, theirs, elasticity
):
    store, capture = pair(our_price=ours, rival_price=theirs)
    result = compare_rival(store, capture, elasticity=elasticity)
    expected = theirs / ours
    assert result.price_index == pytest.approx(expected, rel=1e-12, abs=0)
    assert result.prices[0].ratio == pytest.approx(expected, rel=1e-12, abs=0)
    assert result.price_index > 0 and math.isfinite(result.price_index)
    assert result.suggested_pull_factor == pytest.approx(
        round(min(1.5, max(0.67, (ours / theirs) ** elasticity)), 3)
    )


@pytest.mark.parametrize("aliases", [None, {}, {"Unrelated": "🍵"}])
def test_an_absent_alias_does_not_match_a_symbol_only_product(aliases):
    store, capture = pair(our_name="🍵", rival_name="Other product")
    result = compare_rival(store, capture, aliases=aliases)
    assert result.matched == 0 and result.prices == [] and result.price_index is None
    assert unmatched_names(store, capture) == (["Other product"], ["🍵"])


@pytest.mark.parametrize("ours,theirs", [("🍵", "🍫"), ("!!!", "???"), ("🛒", "🧃")])
def test_different_symbol_names_are_not_equivalent(ours, theirs):
    store, capture = pair(our_name=ours, rival_name=theirs)
    result = compare_rival(store, capture)
    assert result.matched == 0 and result.price_index is None
    assert unmatched_names(store, capture) == ([theirs], [ours])


@pytest.mark.parametrize("name", ["🍵", "!!!", "Tea"])
def test_a_real_exact_or_explicit_match_is_counted(name):
    store, capture = pair(our_name=name, rival_name=name)
    assert compare_rival(store, capture).matched == 1
    capture.items[0].name = "Different label"
    result = compare_rival(store, capture, aliases={"Different label": name})
    assert result.matched == 1 and result.price_index == 1
