"""A saved store schedule admits arrivals only in its open half-open windows."""

import asyncio
import json
from collections import Counter

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine.generators.arrivals import generate_customers
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner
from tests.engine.test_reproducibility import _RecordingEngine


def _person(day, hour):
    return Persona(id=f'd{day}-h{hour}', day=Weekday(day), arrival_hour=hour, identity='shopper', age_group='20s',
                   gender='Female', description='Offline schedule test', intent='browse', purpose='browse')


def _runner():
    engine = _RecordingEngine()
    return PerCustomerSimulationRunner(SimulationConfig(seed=19), engine, AStarPathFinder(), sample_cue, BEHAVIOR_PATTERNS), engine


@pytest.mark.parametrize('weekday', range(1, 8))
@pytest.mark.parametrize('opening,closing', [(0, 24), (0, 1), (9, 10), (23, 24)])
def test_every_weekday_and_hour_respects_opening_boundaries(weekday, opening, closing):
    store = generate_store('station_kiosk')
    store.weekly_schedule = [DaySchedule(day=Weekday(day), is_open=day == weekday, open_hour=opening, close_hour=closing) for day in range(1, 8)]
    people = [_person(day, hour) for day in range(1, 8) for hour in range(24)]
    runner, _ = _runner()
    _, entries, counts = runner._validate_and_prepare(store, people)
    assert {entry.persona_id for entry, _ in entries} == {f'd{weekday}-h{hour}' for hour in range(opening, closing)}
    assert counts == Counter({(Weekday(weekday), hour): 1 for hour in range(opening, closing)})
    original = {entry.persona_id: entry.arrival_time for entry in generate_customers(people, seed=runner.run_seed)}
    assert all(entry.arrival_time == original[entry.persona_id] for entry, _ in entries)


def test_absent_schedule_preserves_legacy_arrivals_but_missing_days_in_an_explicit_schedule_are_closed():
    store = generate_store('station_kiosk')
    people = [_person(1, 0), _person(7, 23)]
    runner, _ = _runner()
    store.weekly_schedule = []
    assert len(runner._validate_and_prepare(store, people)[1]) == 2
    store.weekly_schedule = [DaySchedule(day=Weekday.MON, open_hour=0, close_hour=24)]
    assert [entry.persona_id for entry, _ in runner._validate_and_prepare(store, people)[1]] == ['d1-h0']


def test_closed_arrivals_never_reach_the_engine_or_customer_results():
    store = generate_store('station_kiosk')
    store.weekly_schedule = [DaySchedule(day=Weekday.MON, open_hour=9, close_hour=10), DaySchedule(day=Weekday.SUN, is_open=False)]
    people = [_person(1, 8), _person(1, 9), _person(1, 10), _person(7, 9)]
    before = [person.model_dump() for person in people]
    runner, engine = _runner()
    progress = []
    aggregate, customers = asyncio.run(runner.run(store, people, on_progress=lambda c, f, t: progress.append((c, f, t))))
    assert set(engine.contexts) == {'d1-h9'}
    assert [customer.persona_id for customer in customers] == ['d1-h9']
    assert aggregate.summary.total_customers == 1
    assert aggregate.diagnostics.requested_customers == 1
    assert aggregate.diagnostics.failed_customers == []
    assert progress[-1] == (1, 0, 1)
    assert [person.model_dump() for person in people] == before


def test_all_closed_arrivals_produce_a_valid_empty_run_without_engine_calls():
    store = generate_store('station_kiosk')
    store.weekly_schedule = [DaySchedule(day=Weekday.MON, is_open=False)]
    runner, engine = _runner()
    aggregate, customers = asyncio.run(runner.run(store, [_person(1, 12)]))
    assert customers == [] and engine.contexts == {}
    assert aggregate.summary.total_customers == 0
    assert aggregate.diagnostics.requested_customers == 0
    assert aggregate.diagnostics.failed_customers == []
    json.dumps(aggregate.model_dump(), allow_nan=False)
