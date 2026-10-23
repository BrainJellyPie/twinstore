"""Wandering reaches the endpoint used to plan the next stop without skipping tiles."""

import math
import random

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import JourneyStep, build_journey
from store_emulator.engine.routing.timeline_builder import build_timeline


@pytest.mark.parametrize("diagonal", [False, True])
@pytest.mark.parametrize("dwell", [30, 60, 120])
@pytest.mark.parametrize("seed", [3, 14, 56])
def test_random_glances_do_not_skip_planned_tiles_or_teleport(diagonal, dwell, seed):
    store = generate_store("compact_cvs", seed=0)
    width, height = store.grid_size
    actions = [
        CustomerAction(nav="area", action=Action.WANDER, area=(0, 0, width - 1, height - 1), dwell=dwell),
        CustomerAction(nav="leave"),
    ]
    journey = build_journey(store, actions, AStarPathFinder(diagonal=diagonal), block_move_sec=3)
    original = [step.model_dump() for step in journey]
    result = build_timeline("p", Weekday.MON, "10:00:00", journey, store, rng=random.Random(seed))
    moves = [(event.x, event.y) for event in result.timeline if event.action == Action.MOVE]
    assert moves == [tile for step in journey for tile in step.path[1:]]
    for first, second in zip(result.timeline, result.timeline[1:]):
        assert max(abs(first.x - second.x), abs(first.y - second.y)) <= 1
        assert second.elapsed_sec >= first.elapsed_sec
    assert result.timeline[-1].action == Action.EXIT
    assert [step.model_dump() for step in journey] == original
    assert build_timeline("p", Weekday.MON, "10:00:00", journey, store, rng=random.Random(seed)) == result


@pytest.mark.parametrize("diagonal", [False, True])
@pytest.mark.parametrize("move_seconds", [0.5, 3])
@pytest.mark.parametrize("dwell", [0, 1, 3, 4, 10])
def test_wander_endpoint_fits_actual_walking_time(diagonal, move_seconds, dwell):
    store = Store(id="s", name="Empty", type="test", grid_size=(8, 8))
    action = CustomerAction(nav="area", action=Action.WANDER, area=(7, 7, 7, 7), dwell=dwell)
    journey = build_journey(store, [action], AStarPathFinder(diagonal=diagonal), block_move_sec=move_seconds)
    path = journey[0].path
    walking = sum(math.dist(a, b) * move_seconds for a, b in zip(path, path[1:]))
    assert walking <= dwell
    journey.append(JourneyStep(path=[path[-1]], action=CustomerAction(
        nav="path", target=path[-1], action=Action.BROWSE, dwell=1,
    )))
    result = build_timeline("p", Weekday.MON, "10:00:00", journey, store,
                            block_move_sec=move_seconds, rng=random.Random(3))
    assert result.timeline[-1].elapsed_sec == dwell
    assert (result.timeline[-1].x, result.timeline[-1].y) == path[-1]


def test_glance_timestamp_marks_its_start_and_duration_precedes_next_move():
    store = generate_store("compact_cvs", seed=0)
    width, height = store.grid_size
    journey = build_journey(store, [
        CustomerAction(nav="area", action=Action.WANDER, area=(0, 0, width - 1, height - 1), dwell=120),
        CustomerAction(nav="leave"),
    ], AStarPathFinder(), block_move_sec=3)
    result = build_timeline("p", Weekday.MON, "10:00:00", journey, store, rng=random.Random(3))
    glances = [i for i, event in enumerate(result.timeline) if event.action == Action.WANDER and event.duration]
    assert glances
    for i in glances:
        previous, glance, following = result.timeline[i - 1:i + 2]
        assert glance.elapsed_sec == previous.elapsed_sec
        assert following.elapsed_sec >= glance.elapsed_sec + glance.duration
