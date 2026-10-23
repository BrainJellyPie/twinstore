"""A cloud concurrency cap cannot turn paid customer writing into local, unpriced work."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from store_emulator.application import generation_async as ga
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.generators import persona as gen


def plan(seconds=12):
    return gen.WritePlan(
        visitors={1: 1000}, all=gen.WriteSize(1000, 1000, 101), sample=gen.WriteSize(100, 100, 11),
        probe_seconds=seconds, probe_customers=10, probe_requests=1,
        probe_prompt_tokens=2000, probe_completion_tokens=1000,
    )


def client(base, slots):
    return SimpleNamespace(model="paid-model", api_base=base, max_parallel=slots, get_usage=lambda: TokenUsage())


@pytest.mark.parametrize("base", [None, "https://provider.example/v1", "http://192.168.1.10/v1"])
@pytest.mark.parametrize("slots", [None, 1, 4, 40])
def test_cloud_cost_and_time_respect_actual_endpoint_and_request_cap(monkeypatch, base, slots):
    price = Mock(return_value=0.02)
    monkeypatch.setattr(ga, "cost_usd", price)
    write = plan()
    estimated = ga.write_estimate(client(base, slots), write, write.all)
    assert estimated["cost_usd"] == 2.0
    assert estimated["minutes"] == round(100 * 12 / min(slots or 20, 20) / 60, 1)
    price.assert_called_once_with("paid-model", 2000, 1000)


@pytest.mark.parametrize("base", ["http://localhost:8081/v1", "http://127.0.0.1:8081/v1", "http://[::1]:8081/v1"])
@pytest.mark.parametrize("slots", [None, 1, 4])
def test_loopback_remains_unpriced_and_uses_local_timing(monkeypatch, base, slots):
    price = Mock(side_effect=AssertionError("local model was priced"))
    monkeypatch.setattr(ga, "cost_usd", price)
    write = plan()
    estimated = ga.write_estimate(client(base, slots), write, write.all)
    assert estimated["cost_usd"] is None
    assert estimated["minutes"] == round(100 * 12 / (1 + .5 * max(0, (slots or 1) - 1)) / 60, 1)


@pytest.mark.parametrize("slots", [1, 4, 40])
def test_fast_paid_cloud_write_still_asks_about_cost(monkeypatch, slots):
    monkeypatch.setattr(ga, "cost_usd", lambda *args: .02)
    status, choice = Mock(), AsyncMock(return_value="sample")
    monkeypatch.setattr(ga, "write_status", status)
    monkeypatch.setattr(ga, "_await_choice", choice)
    result = asyncio.run(ga._decide("project", "generation", client(None, slots), plan(seconds=.1)))
    assert result == 100
    choice.assert_awaited_once()
    confirm = status.call_args_list[0].kwargs["progress"]["confirm"]
    assert confirm["local"] is False
    assert confirm["all"]["cost_usd"] == 2.0


@pytest.mark.parametrize("base,slots,local", [
    (None, 1, False), (None, None, False),
    ("http://127.0.0.1:8081/v1", None, True), ("http://127.0.0.1:8081/v1", 4, True),
])
def test_batch_pace_follows_endpoint_instead_of_concurrency(monkeypatch, tmp_path, base, slots, local):
    monkeypatch.chdir(tmp_path)
    seen = []
    usual = gen.Pace(daily_cap=1000, batch_size=10)

    async def generate(*args, pace, **kwargs):
        seen.append(pace(usual))
        return []

    monkeypatch.setattr(ga, "assistive_client", lambda *args, **kwargs: client(base, slots))
    monkeypatch.setattr(ga.gen_persona, "generate_batched", generate)
    asyncio.run(ga._run_async_pipeline(
        config=SimulationConfig(), project_id="project", meta={}, schedules=[], custom_instruction="",
        supplemental_bytes=None, supplemental_filename="",
    ))
    assert seen == [ga.LOCAL_MODEL_PACE if local else usual]
