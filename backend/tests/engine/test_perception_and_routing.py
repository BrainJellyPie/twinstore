from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import PerceptionConfig
from store_emulator.domain.rack import Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face
from store_emulator.engine.routing.route_builder import (
    JourneyStep, integrate_actions, perceive_products,
)


def _aisle_store() -> Store:
    """7x3 store. Shelf S at (3, 1) carries sku-n on its N face and sku-s on its S face.

    x:  0    1    2    3    4    5    6
    y0  .    .    .    .    .    .    .      ← aisle north of the shelf
    y1  EN   .    .    [S]  .    .    EX
    y2  .    .    .    .    .    .    .      ← aisle south of the shelf
    """
    shelf = Rack(
        id="S", type=RackType.SHELF, shape=[[1]], position=(3, 1),
        slots=[
            Slot(block=0, face=Face.N, level=3, items=[SlotItem(sku="sku-n", name="north item", price=100)]),
            Slot(block=0, face=Face.S, level=1, items=[SlotItem(sku="sku-s", name="south item", price=100)]),
        ],
    )
    return Store(
        id="aisle", name="aisle", type="convenience", grid_size=(7, 3),
        racks=[
            shelf,
            Rack(id="en", type=RackType.ENTRANCE, shape=[[1]], position=(0, 1)),
            Rack(id="ex", type=RackType.EXIT, shape=[[1]], position=(6, 1)),
        ],
    )


def _walk(*tiles: tuple[int, int]) -> list[JourneyStep]:
    return [JourneyStep(action=CustomerAction(nav="path", target=tiles[-1]), path=list(tiles))]


def test_visibility_only_sees_the_face_it_walks_past():
    store = _aisle_store()
    seen = perceive_products(store, _walk((0, 0), (1, 0), (2, 0), (3, 0), (4, 0)), PerceptionConfig())
    skus = {e.sku for e in seen}
    assert "sku-n" in skus          # walked right past the north face
    assert "sku-s" not in skus      # the south face points away from the north aisle


def test_visibility_falls_off_with_distance_and_level():
    store = _aisle_store()
    perception = PerceptionConfig(min_visibility=0.0)
    front = perceive_products(store, _walk((3, 0)), perception)
    oblique = perceive_products(store, _walk((5, 0)), perception)  # lateral offset 2 at depth 1 → outside the cone
    assert front and front[0].sku == "sku-n"
    assert not oblique
    south = perceive_products(store, _walk((3, 2)), perception)
    # Same distance, but the south slot is on L1 (bottom shelf) → lower attention than L3.
    assert south[0].visibility < front[0].visibility


def test_line_of_sight_is_blocked_by_racks():
    # Shelf at (3, 2) faces north; a shopper at (3, 0) looks at it from two tiles away.
    def store_with(blocked: bool) -> Store:
        base = _aisle_store()
        racks = [base.racks[0].model_copy(update={"position": (3, 2)}), *base.racks[1:]]
        if blocked:
            racks.append(Rack(id="B", type=RackType.SHELF, shape=[[1]], position=(3, 1)))
        return base.model_copy(update={"grid_size": (7, 4), "racks": racks})

    perception = PerceptionConfig(view_distance=2, min_visibility=0.0)
    clear = perceive_products(store_with(False), _walk((3, 0)), perception)
    blocked = perceive_products(store_with(True), _walk((3, 0)), perception)
    assert any(e.sku == "sku-n" for e in clear)
    assert not any(e.sku == "sku-n" for e in blocked)


def test_multiple_facings_raise_visibility():
    store = _aisle_store()
    # sku-s sits on the bottom shelf (L1): one facing is noticed with probability < 1.
    extra = Rack(
        id="T", type=RackType.SHELF, shape=[[1]], position=(5, 1),
        slots=[Slot(block=0, face=Face.S, level=1, items=[SlotItem(sku="sku-s", name="south item", price=100)])],
    )
    store.racks.append(extra)
    path = _walk((3, 2), (4, 2), (5, 2))
    one = next(e for e in perceive_products(_aisle_store(), path, PerceptionConfig()) if e.sku == "sku-s")
    both = next(e for e in perceive_products(store, path, PerceptionConfig()) if e.sku == "sku-s")
    assert one.facings == 1 and both.facings == 2
    assert one.visibility < both.visibility < 1.0


def test_planned_ordering_keeps_shopper_order_and_inserts_impulse_on_the_way(collision_store):
    enter = CustomerAction(nav="path", target=(0, 2), action=Action.ENTER)
    far = CustomerAction(nav="path", target=(3, 0), face=Face.W, action=Action.BROWSE, description="far first")
    near = CustomerAction(nav="path", target=(1, 0), face=Face.E, action=Action.BROWSE, description="near second")
    leave = CustomerAction(nav="leave", action=Action.EXIT)
    impulse = CustomerAction(nav="path", target=(2, 1), face=Face.S, action=Action.BROWSE, origin="impulse")

    planned = integrate_actions(collision_store, [enter, far, near, leave], [impulse], ordering="planned")
    middle = [a.description or a.origin for a in planned[1:-1]]
    assert middle.index("far first") < middle.index("near second")  # shopper's order kept
    assert "impulse" in middle

    greedy = integrate_actions(collision_store, [enter, far, near, leave], [], ordering="nearest")
    assert [a.description for a in greedy[1:-1]] == ["near second", "far first"]  # legacy behavior unchanged


def test_impulse_browse_and_buy_on_one_rack_stay_together(collision_store):
    enter = CustomerAction(nav="path", target=(0, 2), action=Action.ENTER)
    leave = CustomerAction(nav="leave", action=Action.EXIT)
    browse = CustomerAction(nav="path", target=(1, 0), face=Face.W, action=Action.BROWSE, origin="impulse")
    buy = CustomerAction(nav="path", target=(1, 0), face=Face.W, action=Action.BUY, product_sku="sku-b", origin="impulse")
    out = integrate_actions(collision_store, [enter, leave], [browse, buy], ordering="planned")
    kinds = [a.action for a in out]
    assert kinds == [Action.ENTER, Action.BROWSE, Action.BUY, Action.EXIT]
