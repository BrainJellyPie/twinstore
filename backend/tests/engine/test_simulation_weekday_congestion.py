"""Congestion counts belong to one weekday/hour, including only admitted arrivals."""

import asyncio
from collections import Counter

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner
from tests.engine.test_reproducibility import _RecordingEngine


@pytest.mark.parametrize('hour', [0, 12, 23])
@pytest.mark.parametrize('schedule_mode', ['legacy', 'all-day', 'restricted'])
def test_other_weekdays_never_inflate_hourly_congestion(hour, schedule_mode):
    store = generate_store('station_kiosk')
    store.weekly_schedule = [] if schedule_mode == 'legacy' else [
        DaySchedule(day=Weekday(day), is_open=schedule_mode != 'restricted' or day % 2 == 1,
                    open_hour=hour if schedule_mode == 'restricted' else 0,
                    close_hour=hour + 1 if schedule_mode == 'restricted' else 24)
        for day in range(1, 8)
    ]
    people = [Persona(id=f'd{day}-p{i}', day=Weekday(day), arrival_hour=hour, identity='shopper', age_group='20s',
                      gender='Female', description='Offline congestion check', intent='browse', purpose='browse')
              for day in range(1, 8) for i in range(day)]
    people += [person.model_copy(update={'id': person.id + '-other-hour', 'arrival_hour': (hour + 1) % 24}) for person in people]
    expected_people = [person for person in people if schedule_mode != 'restricted' or (person.day % 2 == 1 and person.arrival_hour == hour)]
    expected = Counter((person.day, person.arrival_hour) for person in expected_people)
    engine = _RecordingEngine()
    runner = PerCustomerSimulationRunner(SimulationConfig(seed=31), engine, AStarPathFinder(), sample_cue, BEHAVIOR_PATTERNS)
    asyncio.run(runner.run(store, people))
    assert set(engine.contexts) == {person.id for person in expected_people}
    for context in engine.contexts.values():
        assert context.concurrent_visitors_in_hour == expected[(context.day, context.arrival_hour)]
