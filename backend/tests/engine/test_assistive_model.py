"""Assistive features (interviews, commentary, set-up helpers) use a provider that has a key when the app's text
model has none; simulation runs never fall back."""

import pytest

from store_emulator.application.providers import assistive_model, text_model_fallback
from store_emulator.domain.config import LLMConfig

KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DASHSCOPE_API_KEY", "OPENROUTER_API_KEY")


@pytest.fixture
def keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no saved provider settings
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)

    def set_keys(*names: str) -> None:
        for n in names:
            monkeypatch.setenv(n, "test-key")
    return set_keys


def test_a_text_model_without_a_key_falls_back_to_a_fast_model_that_has_one(keys):
    keys("ANTHROPIC_API_KEY")
    config = LLMConfig(model="gemini/gemini-3.1-pro-preview")
    assert assistive_model("", config) == "anthropic:claude-haiku-5-5"
    assert assistive_model("  openai:gpt-6-sol ", config) == "openai:gpt-6-sol"  # an explicit pick always wins
    assert text_model_fallback("anthropic:claude-opus-5-5") is None  # its provider has a key


def test_the_text_model_is_kept_when_it_has_a_key_or_nothing_else_does(keys):
    assert assistive_model("", LLMConfig(model="gemini/gemini-3.1-pro-preview")) == "gemini/gemini-3.1-pro-preview"
    keys("GEMINI_API_KEY", "OPENAI_API_KEY")
    assert assistive_model("", LLMConfig(model="gemini/gemini-3.1-pro-preview")) == "gemini/gemini-3.1-pro-preview"
    assert text_model_fallback("anthropic:claude-haiku-5-5") == "openai:gpt-6-luna"
    assert text_model_fallback("ollama_chat/qwen3.5:2b") is None  # local models need no key


@pytest.mark.parametrize(('primary', 'alternative_key'), [
    ('gemini/gemini-3.1-pro-preview', 'ANTHROPIC_API_KEY'),
    ('anthropic/claude-haiku-5-5', 'OPENAI_API_KEY'),
    ('openai/gpt-6-luna', 'GEMINI_API_KEY'),
])
def test_an_explicit_config_key_keeps_the_apps_model(keys, primary, alternative_key):
    from pydantic import SecretStr
    keys(alternative_key)
    config = LLMConfig(model=primary, api_key=SecretStr('fake-direct-config-key'))
    assert assistive_model('', config) == primary


def test_a_run_on_a_model_without_a_key_is_refused_before_it_starts(keys, monkeypatch):
    from store_emulator.application.providers import ensure_resolvable
    from store_emulator.domain.config import EngineType, SimulationConfig

    config = SimulationConfig(engine_type=EngineType.PATTERN_INTENT_IMPULSE, llm=LLMConfig(model="gemini/gemini-3.1-pro-preview"))
    with pytest.raises(ValueError, match=r"No API key for Google Gemini .* Use rule-based shoppers"):
        ensure_resolvable(config)
    keys("ANTHROPIC_API_KEY")
    with pytest.raises(ValueError, match=r"Pick another model for this run \(anthropic:claude-haiku-5-5 has a key\)"):
        ensure_resolvable(config)
    keys("GEMINI_API_KEY")
    ensure_resolvable(config)
    custom = SimulationConfig(engine_type=EngineType.PATTERN_INTENT_IMPULSE,
                              llm=LLMConfig(model="openai/served-model", api_base="http://127.0.0.1:9000/v1"))
    from store_emulator.application import local_vlm
    with pytest.raises(ValueError, match=r"No model server answers at http://127.0.0.1:9000/v1"):
        ensure_resolvable(custom)  # nothing runs there: every shopper would fail
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: True)
    ensure_resolvable(custom)  # a self-hosted endpoint needs no cloud key


def test_the_engine_list_says_when_a_default_model_has_no_key(keys, monkeypatch):
    from fastapi.testclient import TestClient

    from store_emulator.server import deps
    from store_emulator.server.main import app

    monkeypatch.setattr(deps, "_config", None)
    keys("OPENAI_API_KEY")
    with TestClient(app) as client:
        engines = {e["engine_type"]: e for e in client.get("/api/engines").json()}
        llm = engines["pattern_intent_impulse"]
        assert llm["model"] == "anthropic/claude-haiku-5-5" and llm["model_ready"] is False
        assert llm["suggested_model"] == "openai:gpt-6-luna"
        assert engines["rule_based"]["model_ready"] is True and engines["rule_based"]["suggested_model"] == ""
        keys("ANTHROPIC_API_KEY")
        llm = {e["engine_type"]: e for e in client.get("/api/engines").json()}["pattern_intent_impulse"]
        assert llm["model_ready"] is True and llm["suggested_model"] == ""
        # The vision default is the model on this computer: ready only when its server answers.
        from store_emulator.application import local_vlm
        monkeypatch.setattr(local_vlm, "server_answers", lambda base: False)
        assert {e["engine_type"]: e for e in client.get("/api/engines").json()}["vlm_glance"]["model_ready"] is False
        monkeypatch.setattr(local_vlm, "server_answers", lambda base: True)
        assert {e["engine_type"]: e for e in client.get("/api/engines").json()}["vlm_glance"]["model_ready"] is True


def test_a_run_on_the_local_model_when_it_is_turned_off_says_so(monkeypatch):
    from store_emulator.application import local_vlm, providers

    class _Off:
        def status(self):
            return local_vlm.LocalVLMStatus(state="disabled", message="turned off by TWINSTORE_LOCAL_VLM")

    monkeypatch.setattr(local_vlm, "manager", lambda: _Off())
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: False)
    with pytest.raises(ValueError, match=r"turned off \(TWINSTORE_LOCAL_VLM\)\. Add an API key") as raised:
        providers.ensure_local_ready("http://127.0.0.1:8081/v1")
    assert "Start it in Settings" not in str(raised.value)


def test_prompt_listings_put_products_the_question_names_first_and_share_the_rest():
    from store_emulator.engine.prompting import relevant_first

    entries = [("Drinks", f"Cola {i}", f"cola{i}") for i in range(5)] + [("Snacks", f"Chips {i}", f"chips{i}") for i in range(5)] \
        + [("Ice cream", "Vanilla pint", "vanilla"), ("Ice cream", "Cookie dough pint", "dough")]
    assert relevant_first(entries, "Would ice creams sell more at eye level?", 4) == ["vanilla", "dough", "cola0", "chips0"]
    assert relevant_first(entries, "", 3) == ["cola0", "chips0", "vanilla"]
    assert len(relevant_first(entries, "", 50)) == 12


def test_haiku_is_the_default_text_model(keys, monkeypatch):
    from store_emulator.application.config import local_config

    for env in ("PARASTORE_LLM_MODEL", "PARASTORE_LLM_API_BASE"):
        monkeypatch.delenv(env, raising=False)
    assert LLMConfig().model == "anthropic/claude-haiku-5-5"
    assert local_config().llm.model == "anthropic/claude-haiku-5-5"


def test_with_no_cloud_key_the_local_model_answers_text_once_it_is_ready(keys, monkeypatch):
    from store_emulator.application import local_vlm, providers
    from store_emulator.application.local_vlm import LocalVLMStatus

    config = LLMConfig(model="anthropic/claude-haiku-5-5")
    # Nothing set up: nothing to fall back to.
    assert assistive_model("", config) == "anthropic/claude-haiku-5-5"
    providers.use_local_server("http://127.0.0.1:8081/v1")
    state = {"now": "downloading"}

    class _Manager:
        def status(self) -> LocalVLMStatus:
            return LocalVLMStatus(state=state["now"])  # type: ignore[arg-type]

    monkeypatch.setattr(local_vlm, "manager", lambda: _Manager())
    assert text_model_fallback(config.model) is None          # still downloading
    state["now"] = "ready"
    assert assistive_model("", config) == "llamacpp:local"
    resolved = providers.resolve_model("llamacpp:local", base=config)
    assert resolved.model == "openai/local-model" and resolved.api_base == "http://127.0.0.1:8081/v1"
    # A cloud key, when there is one, still comes first.
    keys("OPENAI_API_KEY")
    assert assistive_model("", config) == "openai:gpt-6-luna"


def test_a_run_without_a_key_names_the_local_model_when_it_is_ready(keys, monkeypatch):
    from store_emulator.application import local_vlm, providers
    from store_emulator.application.local_vlm import LocalVLMStatus
    from store_emulator.application.providers import ensure_resolvable
    from store_emulator.domain.config import EngineType, SimulationConfig

    providers.use_local_server("http://127.0.0.1:8081/v1")
    monkeypatch.setattr(local_vlm, "manager", lambda: type("M", (), {"status": lambda self: LocalVLMStatus(state="ready")})())
    config = SimulationConfig(engine_type=EngineType.PATTERN_INTENT_IMPULSE)
    with pytest.raises(ValueError, match=r"Pick the local model on this computer for this run \(llamacpp:local\)"):
        ensure_resolvable(config)
