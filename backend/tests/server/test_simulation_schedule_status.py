"""Saved inputs, progress and results describe the same admitted visitor population."""

import json

import pytest

from store_emulator.application.simulation import RunOptions, run_simulation_background
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine.layout_gen import generate_store


@pytest.mark.parametrize('open_monday', [False, True])
def test_background_run_keeps_saved_inputs_and_completed_counts_in_sync(tmp_path, monkeypatch, open_monday):
    monkeypatch.chdir(tmp_path)
    store = generate_store('station_kiosk')
    store.weekly_schedule = [DaySchedule(day=Weekday.MON, is_open=open_monday, open_hour=9, close_hour=10)]
    people = [Persona(id=f'd{day}-h{hour}', day=Weekday(day), arrival_hour=hour, identity='shopper', age_group='20s',
                      gender='Female', description='Offline admission test', intent='browse', purpose='browse')
              for day, hour in [(1, 8), (1, 9), (1, 10), (7, 9)]]
    run_simulation_background('proj_schedule', 'run_schedule', 'setup_schedule', store, people,
                              SimulationConfig(engine_type=EngineType.RULE_BASED), options=RunOptions(preview=True))
    root = tmp_path / '.data' / 'proj_schedule' / 'runs' / 'run_schedule'
    status = json.loads((root / 'status.json').read_text())
    if not open_monday:   # nobody can come: the run says so instead of finishing with nobody
        assert status['status'] == 'failed' and status['error'].startswith('No shoppers come on')
        return
    assert status['status'] == 'completed', status.get('error')
    expected = int(open_monday)
    assert status['total_customers'] == status['completed_customers'] == expected
    saved_people = json.loads((root / 'input' / 'personas.json').read_text())
    assert {p['id'] for p in saved_people} == ({'d1-h9'} if open_monday else set())
