import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.route_builder import JourneyStep
from store_emulator.engine.routing.timeline_builder import build_timeline


def _single_step(action: CustomerAction, *, path_tile=(1, 0)) -> list[JourneyStep]:
    return [JourneyStep(path=[path_tile], action=action)]


def _run(store, action, **kwargs):
    journey = _single_step(action, **kwargs)
    return build_timeline(
        persona_id="p1",
        day=Weekday.FRI,
        arrival_time="10:00:00",
        journey=journey,
        store=store,
    )


def _buy_events(result):
    return [e for e in result.timeline if e.action == Action.BUY]


def _browse_events(result):
    return [e for e in result.timeline if e.action == Action.BROWSE]


def test_buy_target_rack_follows_sku_not_coordinate(collision_store):
    # sku-b lives on rack B; rack A wins the coordinate first-match.
    action = CustomerAction(
        nav="path", action=Action.BUY, target=(1, 0), face=Face.W,
        product_sku="sku-b", dwell=10,
    )
    buys = _buy_events(_run(collision_store, action))
    assert len(buys) == 1
    assert buys[0].target_rack == "B"
    assert buys[0].product_name == "B item"
    assert buys[0].price == 200


def test_buy_target_rack_correct_even_when_face_is_none(collision_store):
    # Critical: if the LLM omits face, SKU still pins the rack.
    action = CustomerAction(
        nav="path", action=Action.BUY, target=(1, 0), face=None,
        product_sku="sku-b", dwell=10,
    )
    buys = _buy_events(_run(collision_store, action))
    assert buys[0].target_rack == "B"


def test_buy_target_rack_correct_when_target_lands_on_rack_body(collision_store):
    # If the action.target accidentally lands inside rack A's body (0, 0),
    # rack_id_at would return A. The SKU override must still win.
    action = CustomerAction(
        nav="path", action=Action.BUY, target=(0, 0), face=Face.W,
        product_sku="sku-b", dwell=10,
    )
    buys = _buy_events(_run(collision_store, action, path_tile=(0, 0)))
    assert buys[0].target_rack == "B"


def test_buy_does_not_attribute_to_counter(collision_store):
    # Customer's target tile (4, 1) is Counter's exclusive S-face access tile.
    # Pre-fix `rack_id_at((4, 1))` returns "Counter" (only owner) and the
    # BUY's `target_rack` would be Counter. The SKU override must steer it
    # to rack B (where sku-b actually lives) even though no Counter is
    # involved in B's geometry.
    action = CustomerAction(
        nav="path", action=Action.BUY, target=(4, 1), face=Face.N,
        product_sku="sku-b", dwell=10,
    )
    buys = _buy_events(_run(collision_store, action, path_tile=(4, 1)))
    assert buys[0].target_rack == "B"
    assert buys[0].target_rack != "Counter"


def test_buy_multi_placement_uses_stance(multi_placement_store):
    # sku-x is on both P and Q; customer at (1, 0) facing W reached Q.
    action = CustomerAction(
        nav="path", action=Action.BUY, target=(1, 0), face=Face.W,
        product_sku="sku-x", dwell=10,
    )
    buys = _buy_events(_run(multi_placement_store, action))
    assert buys[0].target_rack == "Q"


def test_browse_target_rack_uses_face(collision_store):
    action = CustomerAction(
        nav="path", action=Action.BROWSE, target=(1, 0), face=Face.W, dwell=5,
    )
    browses = _browse_events(_run(collision_store, action))
    assert len(browses) == 1
    assert browses[0].target_rack == "B"


def test_browse_without_face_falls_back_to_first_match(collision_store):
    # face=None: behavior is unchanged from pre-fix (first rack in store.racks).
    # Not ideal, but documented and stable until prompts are tightened.
    action = CustomerAction(
        nav="path", action=Action.BROWSE, target=(1, 0), face=None, dwell=5,
    )
    browses = _browse_events(_run(collision_store, action))
    assert browses[0].target_rack == "A"

@pytest.mark.parametrize("browse_face, buy_face, expected_pick", [
    (Face.W, Face.W, 2), (Face.E, Face.W, 12), (Face.E, None, 12),
])
def test_shelf_dwell_uses_resolved_rack_and_only_continues_the_same_shelf(
    collision_store, browse_face, buy_face, expected_pick,
):
    store = collision_store.model_copy(deep=True)
    for rack in store.racks:
        rack.dwell_min = 12 if rack.id == "B" else 5
    journey = [
        JourneyStep(path=[(1, 0)], action=CustomerAction(
            nav="path", action=Action.BROWSE, target=(1, 0), face=browse_face, dwell=2,
        )),
        JourneyStep(path=[(1, 0)], action=CustomerAction(
            nav="path", action=Action.BUY, target=(1, 0), face=buy_face, product_sku="sku-b", dwell=2,
        )),
    ]
    result = build_timeline("p1", Weekday.FRI, "10:00:00", journey, store)
    browse, buy = _browse_events(result)[0], _buy_events(result)[0]
    assert browse.duration == (12 if browse_face == Face.W else 5)
    assert buy.target_rack == "B" and buy.duration == expected_pick
