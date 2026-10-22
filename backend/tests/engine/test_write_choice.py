"""Customers are written for every estimated visitor; above the warning limits the job asks first."""

import asyncio
import threading
import time

import pytest

from store_emulator.domain.persona import Persona
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import TokenUsage, Weekday
from store_emulator.engine.generators import persona as gen


def _patch_day(monkeypatch: pytest.MonkeyPatch, asked: list[tuple[int, list[tuple[int, int]]]]) -> None:
    async def analyze_location(llm, *a, **k):
        return gen.TradeAreaProfile(keywords=["k"], identities=["i"], purposes=["p"])

    async def analyze_daily_traffic(llm, address, profile, profile_, day, open_hour, close_hour):
        return [gen.HourlyProfile(hour=h, visitor_count=50, person_types=["student"]) for h in range(open_hour, close_hour)]

    async def for_day(llm, address, profile, day, hourly, **k):
        hours = [(h.hour, h.visitor_count) for h in hourly if h.visitor_count > 0]
        asked.append((int(day), hours))
        llm.usage.requests += 1
        llm.usage.prompt_tokens += 1000
        llm.usage.completion_tokens += 300
        if k.get("on_written"):
            k["on_written"](sum(n for _, n in hours))
        made = [(h, i) for h, n in hours for i in range(n)]   # ids per call from 1, as the writer numbers them
        return [Persona(id=f"F{int(day)}{k:03d}", day=day, arrival_hour=h, identity="student", age_group="20s",  # type: ignore[arg-type]
                        gender="Female", description=f"{int(day)}-{h}-{i}", intent="i", purpose="p")
                for k, (h, i) in enumerate(made, start=1)]

    monkeypatch.setattr(gen, "analyze_location", analyze_location)
    monkeypatch.setattr(gen, "analyze_daily_traffic", analyze_daily_traffic)
    monkeypatch.setattr(gen, "generate_personas_for_day", for_day)


class _Client:
    def __init__(self) -> None:
        self.usage = TokenUsage()

    def get_usage(self) -> TokenUsage:
        return self.usage.model_copy()


def test_one_request_is_timed_first_and_the_answer_sets_how_many_a_day_are_written(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[int, list[tuple[int, int]]]] = []
    _patch_day(monkeypatch, asked)
    plans: list[gen.WritePlan] = []

    async def decide(plan: gen.WritePlan) -> int:
        plans.append(plan)
        return plan.sample.per_day

    schedules = [DaySchedule(day=1, is_open=True, open_hour=8, close_hour=12),   # 4 hours × 50 = 200 visitors
                 DaySchedule(day=2, is_open=True, open_hour=8, close_hour=10)]   # 100 visitors
    progress: list[tuple[int, int]] = []
    out = asyncio.run(gen.generate_batched(_Client(), "addr", "profile", schedules, decide=decide,  # type: ignore[arg-type]
                                           on_progress=lambda done, total: progress.append((done, total))))
    (plan,) = plans
    assert plan.visitors == {1: 200, 2: 100}
    assert plan.all == gen.WriteSize(per_day=1000, customers=300, requests=30)
    assert plan.sample == gen.WriteSize(per_day=100, customers=200, requests=22)   # 25 an hour: 3 requests each
    assert (plan.probe_customers, plan.probe_requests, plan.probe_prompt_tokens, plan.probe_completion_tokens) == (10, 1, 1000, 300)
    assert asked[0] == (1, [(8, 10)])   # the probe: one request of the busiest hour
    # Day 1 is written to the sample (100 over 4 hours) less the probe's 10; day 2 has 100 visitors, all sampled.
    assert sorted(asked[1:]) == [(1, [(8, 15), (9, 25), (10, 25), (11, 25)]), (2, [(8, 50), (9, 50)])]
    # Every day still has all its visitors: the rest are twins of the written customers, and ids are unique.
    assert len(out) == 300 and len({p.id for p in out}) == 300
    day1 = [p for p in out if p.day == Weekday(1)]
    assert sum(not p.twin_of for p in day1) == 100 and len(day1) == 200
    assert progress[-1] == (200, 200)


def test_without_a_decision_every_visitor_is_written(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[int, list[tuple[int, int]]]] = []
    _patch_day(monkeypatch, asked)
    schedules = [DaySchedule(day=3, is_open=True, open_hour=8, close_hour=10)]
    out = asyncio.run(gen.generate_batched(_Client(), "addr", "profile", schedules))  # type: ignore[arg-type]
    assert asked == [(3, [(8, 50), (9, 50)])] and len(out) == 100 and not any(p.twin_of for p in out)


class _Llm:
    def __init__(self, model: str, max_parallel: int | None = None, api_base: str | None = None) -> None:
        self.model, self.max_parallel, self.api_base = model, max_parallel, api_base


def _plan(seconds: float) -> gen.WritePlan:
    return gen.WritePlan(
        visitors={1: 500, 2: 500}, all=gen.WriteSize(1000, 1000, 100), sample=gen.WriteSize(100, 200, 20),
        probe_seconds=seconds, probe_customers=10, probe_requests=1, probe_prompt_tokens=2000, probe_completion_tokens=2500,
    )


def test_a_quick_write_starts_without_asking(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from store_emulator.application import generation_async as ga

    monkeypatch.chdir(tmp_path)
    # 99 more requests of 5 s, 20 at a time on a provider: under 1 minute; about 99 × $0.0015 on Haiku-like prices.
    assert asyncio.run(ga._decide("p", "gen_x", _Llm("anthropic/claude-haiku-5-5"), _plan(5.0))) == 1000  # pyright: ignore[reportPrivateUsage]


def test_a_long_write_waits_for_the_users_choice(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from store_emulator.application import generation_async as ga
    from store_emulator.application.errors import AppError
    from store_emulator.application.storage.generations import (
        init_generation,
        read_status,
        write_status,
    )

    monkeypatch.chdir(tmp_path)
    gen_id = init_generation("proj_a", "setup_a", "persona")
    write_status("proj_a", gen_id, "running")
    with pytest.raises(AppError) as not_waiting:
        ga.choose_write_size("proj_a", "setup_a", gen_id, "all")
    assert not_waiting.value.status_code == 409
    llm = _Llm("llamacpp/qwen3.5-0.8b", max_parallel=1, api_base="http://127.0.0.1:8081/v1")

    def answer() -> None:
        for _ in range(100):
            progress = read_status("proj_a", gen_id).get("progress") or {}
            if "confirm" in progress:
                confirm = progress["confirm"]
                # 99 more requests of 40 s, one at a time: 66 minutes, free on this computer.
                assert confirm["local"] is True and confirm["all"]["minutes"] == 66.0
                assert confirm["all"]["cost_usd"] is None and confirm["sample"]["per_day"] == 100
                assert confirm["visitors_per_day"] == {"1": 500, "2": 500} and confirm["days"] == 2
                with pytest.raises(AppError):
                    ga.choose_write_size("proj_a", "setup_b", gen_id, "all")
                ga.choose_write_size("proj_a", "setup_a", gen_id, "sample")
                return
            time.sleep(0.05)

    helper = threading.Thread(target=answer)
    helper.start()
    assert asyncio.run(ga._decide("proj_a", gen_id, llm, _plan(40.0))) == 100  # pyright: ignore[reportPrivateUsage]
    helper.join()
    assert "confirm" not in (read_status("proj_a", gen_id).get("progress") or {})

    write_status("proj_a", gen_id, "running", progress={"confirm": {}})
    ga.choose_write_size("proj_a", "setup_a", gen_id, "cancel")
    with pytest.raises(ValueError, match="canceled"):
        asyncio.run(ga._decide("proj_a", gen_id, llm, _plan(40.0)))  # pyright: ignore[reportPrivateUsage]
