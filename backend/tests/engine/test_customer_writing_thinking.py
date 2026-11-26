"""Writing customers keeps Claude's own thinking; short shopper decisions still answer directly.

Claude Haiku 5.5, asked to answer directly, wrote the ten customers of a request in another order than their rows
(7 of 10 requests failed the row check on all three attempts, so no store could be created). Left to think, 20 of 20
requests passed.
"""

import asyncio

from store_emulator.application import generation_async as ga
from store_emulator.application import providers
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client as lc


def _sent(config: LLMConfig) -> dict[str, object]:
    return lc.LiteLLMClient(config)._call_kwargs(None)  # pyright: ignore[reportPrivateUsage]


def test_customer_generation_does_not_ask_claude_to_answer_directly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lc, "_REJECTED", {})
    monkeypatch.setattr(lc, "_THINKING_OFF", {})
    monkeypatch.setattr(ga, "neighborhood_text", lambda pid: "")
    configs: list[LLMConfig] = []

    def client(requested: str, config: LLMConfig, **kwargs: object) -> object:
        configs.append(config)
        return object()

    async def generate(**kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(ga, "assistive_client", client)
    monkeypatch.setattr(ga, "_generate_personas_impl", generate)
    asyncio.run(ga._run_async_pipeline(  # pyright: ignore[reportPrivateUsage]
        config=SimulationConfig(), project_id="project", meta={"customer_profile": "Customers"},
        schedules=[], custom_instruction="", supplemental_bytes=None, supplemental_filename=""))

    assert len(configs) == 1
    assert configs[0].model == "anthropic/claude-haiku-5-5"
    assert "thinking" not in _sent(configs[0])
    # Every other request to Claude still answers directly.
    assert _sent(LLMConfig(model="anthropic/claude-haiku-5-5"))["thinking"] == {"type": "disabled"}


def test_the_choice_follows_the_model_the_job_ends_up_on(monkeypatch):
    monkeypatch.setattr(lc, "_REJECTED", {})
    monkeypatch.setattr(lc, "_THINKING_OFF", {})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")   # no request is sent
    job = LLMConfig(model="openai/first-choice", claude_thinking=True)
    moved = providers.resolve_model("anthropic:claude-sonnet-5-5", base=job, settings={})
    assert moved.model == "anthropic/claude-sonnet-5-5" and "thinking" not in _sent(moved)
    # It is a runtime choice of the job, not a stored setting.
    assert "claude_thinking" not in job.model_dump()
