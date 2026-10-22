"""An optimization goal read into the optimizer's settings: objective, scope, moves, locked shelves by name and the
smallest gain worth keeping (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Reader:
    def __init__(self, reply: dict[str, object]) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.prompts.append(user_prompt)
        return response_model.model_validate(self.reply)


def test_a_goal_becomes_the_optimizers_settings(client, monkeypatch):
    from store_emulator.application import optimize_goal
    from store_emulator.application.scenarios import (
        _store_for,  # pyright: ignore[reportPrivateUsage]
    )
    store = _store_for(PID, SETUP)
    assert store is not None
    rack = next(r for r in store.racks if r.rack_name and sum(1 for o in store.racks if o.rack_name == r.rack_name) == 1)
    fake = _Reader({"objective": "impulse_revenue", "scope": "both", "max_moves": 5, "keep_fridges_on_walls": True,
                    "locked_shelves": [rack.rack_name, "Moon shelf"], "min_improvement_percent": 2, "rationale": "Impulse, few changes."})
    monkeypatch.setattr(optimize_goal, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/setups/{SETUP}/optimize/goal",
                    json={"text": f"More impulse sales, keep {rack.rack_name} as it is, at most 5 changes"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["objective"], d["scope"], d["max_moves"], d["keep_fridges_on_walls"]) == ("impulse_revenue", "both", 5, True)
    assert d["lock_rack_ids"] == [rack.id] and d["locked"] == [rack.rack_name] and d["min_improvement"] == 0.02
    assert any("Moon shelf" in w for w in d["warnings"]) and fake.prompts[0].startswith("Shelves: ")


def test_out_of_range_limits_are_reported_and_left(client, monkeypatch):
    from store_emulator.application import optimize_goal
    monkeypatch.setattr(optimize_goal, "assistive_client", lambda *a, **k: _Reader({"max_moves": 500, "min_improvement_percent": 250}))
    d = client.post(f"/api/projects/{PID}/setups/{SETUP}/optimize/goal", json={"text": "change everything you can"}).json()
    assert d["objective"] == "revenue_per_visitor" and d["max_moves"] is None and d["min_improvement"] is None
    assert len(d["warnings"]) == 2
