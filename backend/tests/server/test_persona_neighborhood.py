"""Persona generation hears about the project's neighborhood model when there is one."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.store import DaySchedule

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _pipeline(monkeypatch) -> dict[str, object]:
    from store_emulator.application import generation_async
    seen: dict[str, object] = {}

    async def fake_batched(llm, address, profile, **kw):
        seen.update(kw)
        return []

    class _LLM:
        def __init__(self, config: object) -> None:
            seen["model"] = getattr(config, "model", "")

        def get_usage(self):
            from store_emulator.domain.types import TokenUsage
            return TokenUsage()

    monkeypatch.setattr(generation_async.gen_persona, "generate_batched", fake_batched)
    monkeypatch.setattr(generation_async, "LiteLLMClient", _LLM)
    meta = read_json(metadata_path(PID))
    asyncio.run(generation_async._run_async_pipeline(  # pyright: ignore[reportPrivateUsage]
        config=SimulationConfig(), project_id=PID, meta=meta,
        schedules=[DaySchedule(day=1, is_open=True, open_hour=8, close_hour=20)],
        custom_instruction="", supplemental_bytes=None, supplemental_filename=""))
    return seen


def test_personas_follow_the_neighborhood_mix(client, monkeypatch):
    assert "Neighborhood model" not in str(_pipeline(monkeypatch)["supplemental_summary"])
    client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "university", "seed": 1})
    summary = str(_pipeline(monkeypatch)["supplemental_summary"])
    assert "Neighborhood model (university area" in summary and "students" in summary and "busiest hours" in summary
    assert "match this mix" in summary


def test_persona_generation_uses_a_model_that_has_a_key(client, monkeypatch):
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "DASHSCOPE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert str(_pipeline(monkeypatch)["model"]).startswith("anthropic/claude-haiku")
