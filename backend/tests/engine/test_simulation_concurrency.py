"""Reject a closed semaphore before input preparation or CLI file access."""

import asyncio
from unittest.mock import Mock

import pytest

from store_emulator.cli import main
from store_emulator.engine.layout_gen import generate_store
from tests.engine.test_simulation_opening_hours import _person, _runner


@pytest.mark.parametrize("limit", [0, -1, -100])
@pytest.mark.parametrize("has_customers", [False, True])
def test_invalid_concurrency_fails_before_preparing_a_run(monkeypatch, limit, has_customers):
    runner, engine = _runner()
    prepare = Mock(wraps=runner._validate_and_prepare)
    monkeypatch.setattr(runner, "_validate_and_prepare", prepare)
    people = [_person(1, 12)] if has_customers else []

    async def execute():
        with pytest.raises(ValueError, match="max_concurrent must be at least 1"):
            await asyncio.wait_for(runner.run(generate_store("station_kiosk"), people, max_concurrent=limit), 0.25)

    asyncio.run(execute())
    prepare.assert_not_called()
    assert engine.contexts == {}


@pytest.mark.parametrize("limit", [1, 20])
def test_positive_concurrency_completes_all_customers(limit):
    runner, engine = _runner()
    people = [_person(1, hour) for hour in range(10, 15)]
    aggregate, customers = asyncio.run(runner.run(generate_store("station_kiosk"), people, max_concurrent=limit))
    assert aggregate.summary.total_customers == len(customers) == len(people)
    assert set(engine.contexts) == {person.id for person in people}


@pytest.mark.parametrize("limit", ["0", "-1", "-100"])
@pytest.mark.parametrize("command", ["simulate", "ab"])
def test_cli_rejects_invalid_concurrency_before_loading_inputs(capsys, command, limit):
    args = [command, "--out", "unused-output", "--concurrency", limit]
    if command == "ab":
        args += ["--store-a", "missing-a.json", "--store-b", "missing-b.json", "--personas", "missing-personas.json"]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert "--concurrency" in capsys.readouterr().err
