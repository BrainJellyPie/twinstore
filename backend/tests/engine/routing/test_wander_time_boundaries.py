"""Untrusted wander durations obey the prompt's 120-second action budget."""

import math
import random

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import build_journey
from store_emulator.engine.simulation.customer_executor import execute_decision


@pytest.mark.parametrize("dwell", [-10**400, -1, 0, 1, 119, 120, 121, 5000, 86400, 10**400])
@pytest.mark.parametrize("area", [None, (0, 0, 30, 30), (5, 5, 5, 5), (8, 8, 1, 1),
                                  (-100, -100, -90, -90), (-10**100, -10**100, 10**100, 10**100)])
@pytest.mark.parametrize("diagonal", [False, True])
def test_wander_budget_bounds_path_and_elapsed_time_without_changing_input(dwell, area, diagonal):
    store = generate_store("compact_cvs", seed=0)
    action = CustomerAction(nav="area", action=Action.WANDER, dwell=dwell, area=area)
    decision = EngineDecision(engine_type="offline", actions=[action, CustomerAction(nav="leave")])
    original = decision.model_dump()
    bounded = max(0, min(120, dwell))
    control = decision.model_copy(deep=True)
    control.actions[0].dwell = bounded
    finder = AStarPathFinder(diagonal=diagonal)
    expected = execute_decision(store, "p", Weekday.MON, "23:59:50", control, finder, 1,
                                rng=random.Random(7))
    actual = execute_decision(store, "p", Weekday.MON, "23:59:50", decision, finder, 1,
                              rng=random.Random(7))
    assert actual == expected
    journey = build_journey(store, decision.actions, finder, 1)
    walking = sum(math.dist(a, b) for a, b in zip(journey[0].path, journey[0].path[1:]))
    assert walking <= bounded
    assert decision.model_dump() == original
    assert actual.timeline[-1].action == Action.EXIT
    assert actual.duration_sec < 240
    assert all(a.elapsed_sec <= b.elapsed_sec for a, b in zip(actual.timeline, actual.timeline[1:]))


@pytest.mark.parametrize("kind", [None, Action.BROWSE, Action.MOVE])
def test_conflicting_action_labels_cannot_bypass_area_time_budget(kind):
    store = generate_store("compact_cvs", seed=0)
    action = CustomerAction(nav="area", action=kind, dwell=10**400, area=(0, 0, 30, 30))
    journey = build_journey(store, [action, CustomerAction(nav="leave")], AStarPathFinder())
    assert journey[0].action.dwell == 120
    assert action.dwell == 10**400
