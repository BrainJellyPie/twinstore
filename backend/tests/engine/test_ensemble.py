"""Model references, provider settings (keys never leak), and ensemble consumers."""

import asyncio
import json
import random
from pathlib import Path

import pytest
from pydantic import BaseModel

from store_emulator.application import providers
from store_emulator.application.providers import ProviderUpdate, resolve_model
from store_emulator.application.simulation import RunOptions, apply_options
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.providers import EnsembleConfig, EnsembleMember, ModelRef, ProviderKind
from store_emulator.domain.store import Store
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.perception import render_face
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance, combine_votes

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PARASTORE_SETTINGS_DIR", str(tmp_path / "settings"))
    for env in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DASHSCOPE_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    return tmp_path / "settings"


def test_model_ref_parsing():
    assert ModelRef.parse("openai:gpt-6-luna") == ModelRef(provider=ProviderKind.OPENAI, model="gpt-6-luna")
    assert ModelRef.parse("vllm:Qwen/Qwen3.5-9B").model == "Qwen/Qwen3.5-9B"  # type: ignore[union-attr]
    assert ModelRef.parse("gemini/gemini-3.8-flash") is None   # raw LiteLLM id passes through
    assert ModelRef.parse("unknown:model") is None


def test_resolve_needs_a_key_and_never_serializes_it(settings_dir):
    with pytest.raises(ValueError, match="no API key"):
        resolve_model("anthropic:claude-haiku-5-5")
    status = providers.update_provider(ProviderKind.ANTHROPIC, ProviderUpdate(api_key="sk-ant-test-1234567890"))
    assert status.has_key and status.key_source == "settings" and status.key_hint == "…7890"
    assert "sk-ant" not in status.model_dump_json()
    cfg = resolve_model("anthropic:claude-haiku-5-5", base=LLMConfig(temperature=0.2))
    assert cfg.model == "anthropic/claude-haiku-5-5" and cfg.temperature == 0.2
    assert cfg.api_key is not None and cfg.api_key.get_secret_value() == "sk-ant-test-1234567890"
    dumped = json.dumps(SimulationConfig(llm=cfg).model_dump(mode="json"))
    assert "sk-ant" not in dumped and "api_key" not in dumped
    # The settings file is private to the user.
    assert (settings_dir / "providers.json").stat().st_mode & 0o077 == 0
    providers.update_provider(ProviderKind.ANTHROPIC, ProviderUpdate(api_key=""))
    assert not providers.provider_status(ProviderKind.ANTHROPIC).has_key


def test_local_and_openai_compatible_providers_resolve_without_keys(settings_dir, monkeypatch):
    cfg = resolve_model("llamacpp:local")
    assert cfg.model.startswith("openai/") and cfg.api_base == "http://127.0.0.1:8081/v1"
    assert cfg.structured_output == "json_schema"
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-qwen-0000000000")
    qwen = resolve_model("qwen:qwen3.7-plus")
    assert qwen.model == "openai/qwen3.7-plus" and "dashscope" in (qwen.api_base or "")
    providers.update_provider(ProviderKind.VLLM, ProviderUpdate(api_base="http://gpu-box:9000/v1"))
    assert resolve_model("vllm:Qwen/Qwen3.5-9B").api_base == "http://gpu-box:9000/v1"
    refs = {m["ref"] for m in providers.available_models()}
    assert "qwen:qwen3.7-plus" in refs and "llamacpp:local" in refs and not any(r.startswith("openai:") for r in refs)


def test_apply_options_points_the_engine_at_the_chosen_model():
    cfg = apply_options(SimulationConfig(), RunOptions(engine_type=EngineType.VLM_GLANCE, model="qwen:qwen3.7-plus"))
    assert cfg.llm_for(EngineType.VLM_GLANCE).model == "qwen:qwen3.7-plus"
    cfg = apply_options(SimulationConfig(), RunOptions(engine_type=EngineType.PATTERN_INTENT_IMPULSE,
                                                       model="gemini:gemini-3.8-flash"))
    assert cfg.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model == "gemini:gemini-3.8-flash"
    ens = EnsembleConfig(members=[EnsembleMember(model="openai:gpt-6-luna")])
    assert apply_options(SimulationConfig(), RunOptions(ensemble=ens)).ensemble == ens


class _Echo(BaseModel):
    who: str


class _Named:
    def __init__(self, name: str) -> None:
        self.name, self.calls = name, 0

    async def generate_structured_async(self, response_model, system_prompt, user_prompt, *, max_retries=1, seed=None, route=None):
        self.calls += 1
        return response_model.model_validate({"who": self.name})

    async def generate_structured_with_image_async(self, response_model, system_prompt, user_prompt, image_url, *,
                                                   max_retries=1, seed=None, route=None):
        self.calls += 1
        if self.name == "broken":
            raise TimeoutError("down")
        return response_model.model_validate({"who": self.name})

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=self.calls)


def test_mixture_assigns_each_customer_one_member_stably_and_by_weight():
    a, b = _Named("a"), _Named("b")
    ens = EnsembleLLMClient([("a", 3.0, a), ("b", 1.0, b)], seed=7)  # type: ignore[list-item]
    picks = [asyncio.run(ens.generate_structured_async(_Echo, "s", "u", route=f"P{i}")).who for i in range(400)]
    again = [asyncio.run(ens.generate_structured_async(_Echo, "s", "u", route=f"P{i}")).who for i in range(400)]
    assert picks == again
    assert 0.65 < picks.count("a") / 400 < 0.85
    meta = ens.metadata()
    assert {m["name"] for m in meta["members"]} == {"a", "b"}  # type: ignore[index, union-attr]
    assert ens.get_usage().requests == 800


def test_vote_asks_every_member_and_survives_failures():
    ens = EnsembleLLMClient([("a", 1.0, _Named("a")), ("b", 1.0, _Named("b")), ("broken", 1.0, _Named("broken"))],  # type: ignore[list-item]
                            mode="vote")
    answers = asyncio.run(ens.ask_all_with_image(_Echo, "s", "u", "data:image/png;base64,AA=="))
    assert [x.member for x in answers] == ["a", "b", "broken"]
    assert answers[2].answer is None and "TimeoutError" in answers[2].error


def test_combine_votes_majority_and_mean_interest():
    store = Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))
    rack = store.product_racks[0]
    view = render_face(rack, rack.slots[0].face, rng=random.Random(2))
    x, y = view.items[0], view.items[5]
    votes = [
        ("m1", ShelfGlance(product=x.item.name, number=x.mark, interest=8, reason="r1")),
        ("m2", ShelfGlance(product="", number=x.mark, interest=6)),
        ("m3", ShelfGlance(product=y.item.name, number=y.mark, interest=9)),
    ]
    combined, agreement = combine_votes(view, votes)
    assert combined.product == x.item.name and combined.number == x.mark
    assert combined.interest == round((8 + 6) / 3) and combined.reason == "r1"
    assert agreement == pytest.approx(2 / 3)
    nothing, _ = combine_votes(view, [("m1", ShelfGlance()), ("m2", ShelfGlance())])
    assert nothing.product == "" and nothing.interest == 0
