"""Price curves must use shelf offers that survive the simulator's access checks."""

import pytest

from store_emulator.domain.marketing import FocusOutcome, VariantChange, VariantResult
from store_emulator.domain.rack import BlockFace, Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.marketing.experiment import _prices, price_response
from store_emulator.engine.validation import clear_blocked_slots


def layout(obstruction: str, *, available: bool = True, cheap: int = 100) -> Store:
    shelf = Rack(id="shelf", type=RackType.SHELF, shape=[[1]], position=(2, 2), slots=[
        Slot(block=0, face=Face.N, items=[SlotItem(sku="tea", name="Tea", price=cheap)]),
        *([Slot(block=0, face=Face.S, items=[SlotItem(sku="tea", name="Tea", price=300)])] if available else []),
    ])
    racks = [shelf, Rack(id="entrance", type=RackType.ENTRANCE, shape=[[1]], position=(2, 5))]
    if obstruction == "wall":
        shelf.position = (2, 0)
    elif obstruction == "locked":
        shelf.locked_faces = [BlockFace(block=0, face=Face.N)]
    elif obstruction == "occluded":
        shelf.shape = [[1, 1]]
        shelf.slots[0].face = Face.E
    positions = [(2, 1)] if obstruction == "occupied" else [(1, 1), (3, 1), (2, 0)] if obstruction == "unreachable" else []
    racks.extend(Rack(id=f"block{i}", type=RackType.TABLE, shape=[[1]], position=position)
                 for i, position in enumerate(positions))
    return Store(id="store", name="Store", type="convenience", grid_size=(6, 6), racks=racks)


@pytest.mark.parametrize("obstruction", ["wall", "locked", "occupied", "unreachable", "occluded"])
@pytest.mark.parametrize("available", [True, False])
@pytest.mark.parametrize("cheap", [0, 100])
def test_report_prices_match_offers_that_survive_simulation(obstruction: str, available: bool, cheap: int) -> None:
    store = layout(obstruction, available=available, cheap=cheap)
    original = store.model_dump()
    walked = store.model_copy(deep=True)
    cleared = clear_blocked_slots(walked)
    assert len(cleared) == 1  # Confirm the fixture actually exercises an inaccessible facing.
    expected = {"tea": 300} if available else {}
    assert _prices(walked, ["tea"]) == expected
    assert _prices(store, ["tea"]) == expected
    assert store.model_dump() == original


@pytest.mark.parametrize("cheap", [0, 100, 500])
def test_multiple_reachable_offers_keep_the_lowest_price_contract(cheap: int) -> None:
    assert _prices(layout("open", cheap=cheap), ["tea", "missing"]) == {"tea": min(cheap, 300)}


def priced(name: str, price: int | None) -> VariantResult:
    return VariantResult(name=name, prices={"tea": price} if price is not None else {}, focus=[
        FocusOutcome(sku="tea", name="Tea", metric="units", control=1, variant=1,
                     diff=0, rel_diff=0, ci_low=0, ci_high=0, prob_better=0),
    ])


def test_curve_does_not_invent_an_arm_price_from_control() -> None:
    variants = [priced("Cut", 200), priced("Rise", 400), priced("Unavailable", None)]
    changes = {arm.name: [VariantChange(kind="price", sku="tea", price=200)] for arm in variants}
    response = price_response(priced("Control", 300), variants, changes)
    assert response is not None
    assert [(point.arm, point.price) for point in response.points] == [("Cut", 200), ("Control", 300), ("Rise", 400)]


def test_no_curve_without_a_reachable_control_price() -> None:
    variants = [priced("Cut", 200), priced("Rise", 400)]
    changes = {arm.name: [VariantChange(kind="price", sku="tea", price=200)] for arm in variants}
    assert price_response(priced("Control", None), variants, changes) is None
