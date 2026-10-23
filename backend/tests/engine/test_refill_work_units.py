"""A timed refill cannot bring out more units than its allocated work can handle."""

import pytest

from store_emulator.domain.operations import OperationsConfig, OperationsCosts
from store_emulator.engine.simulation.operations_plan import replay
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("crew", [1, 2, 3])
@pytest.mark.parametrize("per_unit", [0, 1, 4, 60])
@pytest.mark.parametrize("per_face", [0, 10, 60])
@pytest.mark.parametrize("reserve", [2, None])
def test_refill_work_covers_units_consumed_while_a_refill_was_underway(crew, per_unit, per_face, reserve):
    shoppers = [_shopper(f"p{i}", arrival, [("chips", 1)]) for i, arrival in enumerate(
        ["10:00:00", "10:00:01", "10:20:00", "10:40:00", "11:00:00"])]
    config = OperationsConfig(crew=crew, stock_per_facing=2, backroom_per_product=reserve,
                              refill_face_sec=per_face, refill_unit_sec=per_unit, checkout_base_sec=1,
                              checkout_item_sec=0, substitute_share=0, crowd_limit=None,
                              patience_sec=7200, patience_sd=0)
    before = [shopper.model_dump() for shopper in shoppers]
    _, report, played = replay(_store(), shoppers, config, OperationsCosts(), seed=1)
    sold = sum(shopper.units_bought for shopper in played)
    assert sold == (4 if reserve is not None else 5)
    refills = [task for task in report.crew_tasks if task.kind == "refill"]
    work = sum(task.end - task.start for task in refills)
    assert report.face_refills == len(refills)
    if per_unit:
        # Finite stock sells both opening units and both backroom units. With an
        # unlimited backroom every one-unit sale triggers a refill to two again.
        moved = sold - 2 if reserve is not None else sold
        assert work - per_face * len(refills) >= moved * per_unit
    else:
        assert work == per_face * len(refills)
        if reserve is not None and per_face:
            assert len(refills) == 1
    assert [shopper.model_dump() for shopper in shoppers] == before


@pytest.mark.parametrize("crew, second_start", [(1, 36072), (2, 36070)])
def test_a_second_pick_cannot_make_extra_refill_units_available_before_their_work_is_done(crew, second_start):
    shoppers = [_shopper(f"p{i}", arrival, [("chips", 1)]) for i, arrival in enumerate(
        ["10:00:00", "10:00:01", "10:01:05", "10:01:06"])]
    config = OperationsConfig(crew=crew, stock_per_facing=2, backroom_per_product=2,
                              refill_face_sec=0, refill_unit_sec=60, checkout_base_sec=1, checkout_item_sec=0,
                              substitute_share=0, crowd_limit=None)
    _, report, played = replay(_store(), shoppers, config, OperationsCosts(), seed=1)
    assert [shopper.total_spent for shopper in played] == [300, 300, 300, 0]
    assert report.lost_units == 1
    assert [(task.start, task.end) for task in report.crew_tasks if task.kind == "refill"] == [
        (36010, 36070), (second_start, second_start + 60),
    ]
    # The solo cashier serves the two already-reserved checkouts before taking
    # another refill. No member can be at the till and shelf at once.
    for member in range(crew):
        tasks = sorted((task.start, task.end) for task in report.crew_tasks if task.member == member)
        assert all(end <= following for (_, end), (following, _) in zip(tasks, tasks[1:]))
