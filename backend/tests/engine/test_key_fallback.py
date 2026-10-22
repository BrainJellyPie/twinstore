"""A key the provider turns down (not valid, revoked) counts as no key: assistive features move on to another provider
with a key, else to the local model on this computer, and runs are refused with a message that says so."""

import asyncio
import urllib.error
from email.message import Message
from io import BytesIO

import litellm
import pytest
from pydantic import BaseModel, SecretStr

from store_emulator.application import local_vlm, providers
from store_emulator.application.local_vlm import LocalVLMStatus
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind
from store_emulator.engine.llm_client import LiteLLMClient, is_auth_error

KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "DASHSCOPE_API_KEY",
        "OPENROUTER_API_KEY")


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no saved provider settings
    monkeypatch.setenv("PARASTORE_SETTINGS_DIR", str(tmp_path / "settings"))
    monkeypatch.delenv("TWINSTORE_LOCAL_VLM_AUTO", raising=False)
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "_REJECTED_KEYS", {})


def _auth_error(provider: str = "gemini") -> litellm.AuthenticationError:
    return litellm.AuthenticationError(
        message='GeminiException - {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", '
                '"status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}',
        llm_provider=provider, model="gemini-3.1-pro-preview")


class _Answer(BaseModel):
    word: str


def test_auth_errors_are_recognised_inside_instructor_retries():
    from instructor.core.exceptions import FailedAttempt, InstructorRetryException

    wrapped = InstructorRetryException("<failed_attempts>…</failed_attempts>", n_attempts=3, total_usage=0,
                                       failed_attempts=[FailedAttempt(1, _auth_error(), None)])
    assert is_auth_error(_auth_error()) and is_auth_error(wrapped)
    assert is_auth_error(RuntimeError("Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error'}}"))
    assert not is_auth_error(RuntimeError("Rate limit exceeded")) and not is_auth_error(ValueError("bad JSON"))


def test_a_turned_down_key_counts_as_none_until_it_is_replaced(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "old-gemini-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-key")
    assert providers.missing_key("gemini/gemini-3.1-pro-preview") is None
    providers.reject_key(ProviderKind.GEMINI, "old-gemini-key")
    assert providers.missing_key("gemini/gemini-3.1-pro-preview") == ProviderKind.GEMINI
    status = providers.provider_status(ProviderKind.GEMINI)
    assert status.has_key and status.key_rejected and not status.ready
    assert providers.cloud_providers_with_key() == ["Anthropic (Claude)"]
    assert providers.text_model_fallback("gemini/gemini-3.1-pro-preview") == "anthropic:claude-haiku-5-5"
    # A new key is tried again; a passing connection test clears the old one too.
    providers.update_provider(ProviderKind.GEMINI, providers.ProviderUpdate(api_key="new-gemini-key"))
    assert providers.missing_key("gemini/gemini-3.1-pro-preview") is None
    providers.update_provider(ProviderKind.GEMINI, providers.ProviderUpdate(api_key=""))
    assert providers.key_rejected(ProviderKind.GEMINI)
    providers.accept_key(ProviderKind.GEMINI, "old-gemini-key")
    assert not providers.key_rejected(ProviderKind.GEMINI)


def test_google_api_key_counts_for_gemini_and_plain_models_carry_the_key_the_app_shows(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    assert providers.provider_status(ProviderKind.GEMINI).has_key
    resolved = providers.resolve_model("gemini/gemini-3.8-flash")
    assert resolved.api_key is not None and resolved.api_key.get_secret_value() == "google-key"
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")  # the documented variable comes first
    assert providers.resolve_model("gemini/gemini-3.8-flash").api_key.get_secret_value() == "gemini-key"  # type: ignore[union-attr]
    # A key entered in Settings reaches LiteLLM for a plain model name too (LiteLLM itself reads only the environment).
    providers.update_provider(ProviderKind.ANTHROPIC, providers.ProviderUpdate(api_key="settings-claude-key"))
    assert providers.resolve_model("anthropic/claude-haiku-5-5").api_key.get_secret_value() == "settings-claude-key"  # type: ignore[union-attr]
    # An endpoint or key in the app configuration is left alone.
    own = LLMConfig(model="x", api_key=SecretStr("config-key"))
    assert providers.resolve_model("anthropic/claude-haiku-5-5", base=own).api_key.get_secret_value() == "config-key"  # type: ignore[union-attr]
    assert providers.resolve_model("openai/served", base=LLMConfig(api_base="http://127.0.0.1:9000/v1")).api_key is None


def test_a_run_on_a_turned_down_key_is_refused_before_it_starts(monkeypatch):
    from store_emulator.domain.config import EngineType, SimulationConfig

    monkeypatch.setenv("GEMINI_API_KEY", "old-gemini-key")
    providers.reject_key(ProviderKind.GEMINI, "old-gemini-key")
    for model in ("gemini/gemini-3.1-pro-preview", "gemini:gemini-3.8-flash"):
        config = SimulationConfig(engine_type=EngineType.PATTERN_INTENT_IMPULSE, llm=LLMConfig(model=model))
        with pytest.raises(ValueError, match=r"Google Gemini turned the API key down .* replace the key in Settings"):
            providers.ensure_resolvable(config)


class _Calls:
    """Instructor stand-in: refuses a model's key, answers on the others."""

    def __init__(self, refused: set[str]) -> None:
        self.refused, self.models = refused, []

    async def create_with_completion(self, *, response_model, messages, max_retries, **kwargs):
        self.models.append(kwargs["model"])
        await asyncio.sleep(0)
        if kwargs["model"] in self.refused:
            raise _auth_error()
        return response_model(word=kwargs["model"]), None


def _patched_use(original, calls: _Calls):
    def use(self, config: LLMConfig) -> None:
        original(self, config)
        self._async_client = type("C", (), {"chat": type("Ch", (), {"completions": calls})()})()
    return use


@pytest.fixture
def fake_calls(monkeypatch):
    """Every LiteLLMClient the test builds talks to one _Calls."""
    calls = _Calls(set())
    original = LiteLLMClient._use  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(LiteLLMClient, "_use", _patched_use(original, calls))
    return calls


def test_an_assistive_call_moves_to_a_provider_that_takes_its_key(monkeypatch, fake_calls):
    monkeypatch.setenv("GEMINI_API_KEY", "old-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    fake_calls.refused = {"gemini/gemini-3.1-pro-preview"}
    client = providers.assistive_client("", LLMConfig(model="gemini/gemini-3.1-pro-preview"))

    async def many() -> list[str]:
        answers = await asyncio.gather(*[client.generate_structured_async(_Answer, "s", f"u{i}") for i in range(4)])
        return [a.word for a in answers]

    assert asyncio.run(many()) == ["openai/gpt-6-luna"] * 4
    assert providers.key_rejected(ProviderKind.GEMINI) and not providers.key_rejected(ProviderKind.OPENAI)
    assert fake_calls.models.count("gemini/gemini-3.1-pro-preview") == 4      # each in-flight call failed once
    # The next client starts on the provider that works.
    assert providers.assistive_model("", LLMConfig(model="gemini/gemini-3.1-pro-preview")) == "openai:gpt-6-luna"


def test_a_run_client_never_moves_on(monkeypatch, fake_calls):
    monkeypatch.setenv("GEMINI_API_KEY", "old-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    fake_calls.refused = {"gemini/gemini-3.1-pro-preview"}
    client = providers.build_client(LLMConfig(model="gemini/gemini-3.1-pro-preview"))
    with pytest.raises(litellm.AuthenticationError):
        asyncio.run(client.generate_structured_async(_Answer, "s", "u"))
    assert not providers.key_rejected(ProviderKind.GEMINI)


class _LocalModel:
    def __init__(self, states: list[str], api_base: str = "http://127.0.0.1:8081/v1") -> None:
        self.states, self.started, self.api_base = states, 0, api_base

    def status(self) -> LocalVLMStatus:
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if state == "ready":
            providers.use_local_server(self.api_base)
        return LocalVLMStatus(state=state, message="Downloading Qwen3.5-2B" if state == "downloading" else "",  # type: ignore[arg-type]
                              progress=0.4 if state == "downloading" else None)

    def start(self) -> LocalVLMStatus:
        self.started += 1
        return self.status()


def test_with_no_other_key_a_background_job_waits_for_the_local_model(monkeypatch, fake_calls):
    monkeypatch.setenv("GEMINI_API_KEY", "old-gemini-key")
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "1")
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    # Port 8081 was busy this time: the server came up elsewhere, after settings were last read.
    providers.use_local_server("http://127.0.0.1:8081/v1")
    local = _LocalModel(["off", "off", "downloading", "downloading", "starting", "ready"], "http://127.0.0.1:53303/v1")
    monkeypatch.setattr(local_vlm, "manager", lambda: local)
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: False)   # nothing left running at 8081
    fake_calls.refused = {"gemini/gemini-3.1-pro-preview"}
    notes: list[str] = []
    client = providers.assistive_client("", LLMConfig(model="gemini/gemini-3.1-pro-preview"), wait=600,
                                        on_wait=notes.append)
    answer = asyncio.run(client.generate_structured_async(_Answer, "s", "u"))
    assert answer.word == "openai/local-model" and client.api_base == "http://127.0.0.1:53303/v1"
    assert local.started == 1
    assert notes and "Google Gemini turned the API key down (API key not valid)" in notes[0] and "(40%)" in notes[0]


def test_a_request_someone_waits_on_says_what_to_do_instead_of_waiting(monkeypatch, fake_calls):
    monkeypatch.setenv("GEMINI_API_KEY", "old-gemini-key")
    monkeypatch.setattr(local_vlm, "manager", lambda: _LocalModel(["downloading"]))
    fake_calls.refused = {"gemini/gemini-3.1-pro-preview"}
    client = providers.assistive_client("", LLMConfig(model="gemini/gemini-3.1-pro-preview"))
    with pytest.raises(ValueError, match=r"turned the API key down .* local model on this computer is getting ready "
                                         r"\(Downloading Qwen3.5-2B \(40%\)\): try again once it is"):
        asyncio.run(client.generate_structured_async(_Answer, "s", "u"))
    monkeypatch.setattr(local_vlm, "manager", lambda: _LocalModel(["off"]))   # not opened from the app icon
    with pytest.raises(ValueError, match=r"Replace the key in Settings → Model providers, or add another provider's key"):
        asyncio.run(client.generate_structured_async(_Answer, "s", "u"))


def test_text_calls_move_on_too(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "old-gemini-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-key")
    seen: list[str] = []

    async def acompletion(**kwargs):
        seen.append(kwargs["model"])
        if kwargs["model"].startswith("gemini/"):
            raise _auth_error()
        return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "hi"})()})()],
                              "usage": None})()

    monkeypatch.setattr(litellm, "acompletion", acompletion)
    client = providers.assistive_client("", LLMConfig(model="gemini/gemini-3.1-pro-preview"))
    assert asyncio.run(client.generate_text_async("s", "u")) == "hi"
    assert seen == ["gemini/gemini-3.1-pro-preview", "anthropic/claude-haiku-5-5"]


def _http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "err", Message(), BytesIO(body.encode()))


def test_keys_are_checked_at_start_without_spending_tokens(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-gemini")
    monkeypatch.setenv("OPENAI_API_KEY", "bad-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "good-claude")
    monkeypatch.setenv("OPENROUTER_API_KEY", "router")
    asked: list[str] = []

    def opener(req):
        asked.append(req.full_url)
        if "googleapis" in req.full_url:
            raise _http_error(400, '{"error": {"details": [{"reason": "API_KEY_INVALID"}]}}')
        if "openai.com" in req.full_url:
            raise _http_error(401)
        if "openrouter" in req.full_url:
            raise urllib.error.URLError("offline")
        return 200

    assert sorted(providers.check_keys(opener)) == ["Google Gemini", "OpenAI"]
    assert all(u.startswith("https://") for u in asked) and not any("key=" in u for u in asked)
    assert providers.cloud_providers_with_key() == ["Anthropic (Claude)", "OpenRouter"]   # offline: no verdict


def test_the_app_starts_the_local_model_when_every_key_is_turned_down(monkeypatch):
    from store_emulator.server import main

    monkeypatch.setenv("GEMINI_API_KEY", "bad-gemini")
    local = _LocalModel(["off"])
    monkeypatch.setattr(main, "local_vlm", lambda: local)
    monkeypatch.setattr(main, "check_keys", lambda: (providers.reject_key(ProviderKind.GEMINI, "bad-gemini"), ["Google Gemini"])[1])
    main._check_keys()  # pyright: ignore[reportPrivateUsage]
    assert local.started == 1


def test_the_persona_job_notes_the_wait_in_its_status(monkeypatch):
    from store_emulator.application import generation_async

    captured: dict[str, object] = {}

    def fake_client(requested, config, *, wait, on_wait):
        captured["wait"] = wait
        on_wait("Google Gemini turned the API key down; waiting for the local model: Downloading (40%)")
        on_wait("Google Gemini turned the API key down; waiting for the local model: Downloading (40%)")
        raise ValueError("stop here")

    writes: list[tuple[object, ...]] = []
    monkeypatch.setattr(generation_async, "assistive_client", fake_client)
    monkeypatch.setattr(generation_async, "write_status", lambda *a, **k: writes.append((*a, k)))
    from store_emulator.domain.config import SimulationConfig
    with pytest.raises(ValueError, match="stop here"):
        asyncio.run(generation_async._run_async_pipeline(  # pyright: ignore[reportPrivateUsage]
            config=SimulationConfig(), project_id="p", meta={}, schedules=[], custom_instruction="",
            supplemental_bytes=None, supplemental_filename="", gen_id="g"))
    assert captured["wait"] >= 1800
    assert writes == [("p", "g", "running", {"progress": {
        "note": "Google Gemini turned the API key down; waiting for the local model: Downloading (40%)"}})]



def test_the_local_model_is_asked_for_fewer_customers_a_day(monkeypatch):
    from store_emulator.domain.store import DaySchedule
    from store_emulator.engine.generators import persona as gen

    asked: list[int] = []
    settled: list[str] = []

    async def analyze_location(llm, *a, **k):
        settled.append("model settled")       # the cap is asked only after the first call
        return gen.TradeAreaProfile(keywords=["k"], identities=["i"], purposes=["p"])

    async def analyze_daily_traffic(*a, **k):
        return [gen.HourlyProfile(hour=h, visitor_count=20, person_types=["student"]) for h in range(8, 18)]

    async def for_day(llm, address, profile, day, hourly, **k):
        asked.append((sum(p.visitor_count for p in hourly), k["batch_size"]))
        return []

    def pace(usual: gen.Pace) -> gen.Pace:
        assert settled, "asked before the first call"
        return gen.Pace(daily_cap=min(usual.daily_cap, 30), batch_size=4)

    monkeypatch.setattr(gen, "analyze_location", analyze_location)
    monkeypatch.setattr(gen, "analyze_daily_traffic", analyze_daily_traffic)
    monkeypatch.setattr(gen, "generate_personas_for_day", for_day)
    schedules = [DaySchedule(day=1, is_open=True, open_hour=8, close_hour=18)]
    asyncio.run(gen.generate_batched(object(), "addr", "profile", schedules, pace=pace))  # type: ignore[arg-type]
    asyncio.run(gen.generate_batched(object(), "addr", "profile", schedules))  # type: ignore[arg-type]
    assert asked == [(30, 4), (100, 10)]

    # Customer generation asks for the local model's cap only when the client ended up on TwinStore's local server.
    from store_emulator.application import generation_async
    from store_emulator.domain.config import SimulationConfig

    caps: list[gen.Pace] = []

    async def batched(llm, *a, pace, **k):
        caps.append(pace(gen.Pace(daily_cap=100, batch_size=10)))
        return []

    class _Client:
        def __init__(self, parallel: int | None) -> None:
            self.max_parallel = parallel

        def get_usage(self):
            from store_emulator.domain.types import TokenUsage
            return TokenUsage()

    monkeypatch.setattr(generation_async.gen_persona, "generate_batched", batched)
    for parallel in (1, None):
        monkeypatch.setattr(generation_async, "assistive_client", lambda *a, p=parallel, **k: _Client(p))
        asyncio.run(generation_async._run_async_pipeline(  # pyright: ignore[reportPrivateUsage]
            config=SimulationConfig(), project_id="p", meta={}, schedules=[], custom_instruction="",
            supplemental_bytes=None, supplemental_filename=""))
    assert caps == [generation_async.LOCAL_MODEL_PACE, gen.Pace(daily_cap=100, batch_size=10)]


def test_requests_to_the_local_server_wait_their_turn_in_the_client(monkeypatch, fake_calls):
    in_flight = [0]
    peak = [0]

    async def create(*, response_model, messages, max_retries, **kwargs):
        in_flight[0] += 1
        peak[0] = max(peak[0], in_flight[0])
        await asyncio.sleep(0.01)
        in_flight[0] -= 1
        return response_model(word="ok"), None

    monkeypatch.setattr(fake_calls, "create_with_completion", create)
    client = LiteLLMClient(LLMConfig(model="openai/local-model", api_base="http://127.0.0.1:8081/v1", max_parallel=2))

    async def many() -> None:
        await asyncio.gather(*[client.generate_structured_async(_Answer, "s", f"u{i}") for i in range(6)])

    asyncio.run(many())
    asyncio.run(many())          # a second event loop gets its own limiter
    assert peak[0] == 2
    assert "max_parallel" not in LLMConfig(max_parallel=2).model_dump()   # runtime only, never written to runs


def test_an_open_day_never_ends_up_without_customers():
    from store_emulator.domain.store import DaySchedule
    from store_emulator.engine.generators import persona as gen

    profile = gen.TradeAreaProfile(keywords=["campus"], identities=["student", "office worker"], purposes=["snack"])
    day = DaySchedule(day=1, is_open=True, open_hour=8, close_hour=22)
    # A small model answered every hour with zero visitors: a plain day of `cap` visitors instead.
    zeros = [gen.HourlyProfile(hour=h, visitor_count=0, person_types=[]) for h in range(24)]
    plain = gen._usable_hourly(zeros, profile, day, 30)  # pyright: ignore[reportPrivateUsage]
    assert [h.hour for h in plain] == list(range(8, 22)) and all(h.person_types == ["student", "office worker"] for h in plain)
    assert 25 <= sum(h.visitor_count for h in plain) <= 40
    counts = {h.hour: h.visitor_count for h in plain}
    assert counts[12] > counts[15] and counts[18] > counts[15]   # lunch and evening peaks
    # Visitors without customer types get the trade area's identities; a good answer is kept as it is.
    untyped = [gen.HourlyProfile(hour=9, visitor_count=4, person_types=[]),
               gen.HourlyProfile(hour=12, visitor_count=6, person_types=["office worker"])]
    fixed = gen._usable_hourly(untyped, profile, day, 30)  # pyright: ignore[reportPrivateUsage]
    assert [(h.visitor_count, h.person_types) for h in fixed] == [(4, ["student", "office worker"]), (6, ["office worker"])]


def test_customer_generation_fails_clearly_when_no_customer_comes_back(monkeypatch):
    from store_emulator.application import generation_async
    from store_emulator.domain.store import DaySchedule

    async def none(*a, **k):
        return []

    class _Client:
        model = "openai/local-model"

        def get_usage(self):
            from store_emulator.domain.types import TokenUsage
            return TokenUsage()

    monkeypatch.setattr(generation_async.gen_persona, "generate_batched", none)
    with pytest.raises(ValueError, match=r"No customers were generated: every request to openai/local-model failed"):
        asyncio.run(generation_async._generate_personas_impl(  # pyright: ignore[reportPrivateUsage]
            _Client(), "addr", "profile", [DaySchedule(day=1, is_open=True, open_hour=8, close_hour=20)]))  # type: ignore[arg-type]
    closed = [DaySchedule(day=1, is_open=False, open_hour=8, close_hour=20)]
    assert asyncio.run(generation_async._generate_personas_impl(_Client(), "addr", "profile", closed)) == []  # type: ignore[arg-type]  # pyright: ignore[reportPrivateUsage]


def test_a_local_server_found_running_is_asked_how_many_requests_it_takes(monkeypatch):
    import json as _json

    class _Resp(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a: object) -> None:
            return None

    urls: list[str] = []

    def opened(answer: object):
        def open_(url: str, timeout: float = 0):
            urls.append(url)
            if isinstance(answer, Exception):
                raise answer
            return _Resp(_json.dumps(answer).encode())
        return type("O", (), {"open": staticmethod(open_)})()

    monkeypatch.setattr(local_vlm, "_DIRECT", opened({"total_slots": 4, "model_path": "x.gguf"}))
    assert local_vlm._server_slots("http://127.0.0.1:8081/v1") == 4  # pyright: ignore[reportPrivateUsage]
    assert urls == ["http://127.0.0.1:8081/props"]
    monkeypatch.setattr(local_vlm, "_DIRECT", opened(OSError("refused")))
    assert local_vlm._server_slots("http://127.0.0.1:8081/v1") == 1  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(local_vlm, "_DIRECT", opened({"model_path": "x.gguf"}))
    assert local_vlm._server_slots("http://127.0.0.1:8081/v1") == 1  # pyright: ignore[reportPrivateUsage]

    # The local model reference carries the slot count of the server TwinStore uses, and only of that one.
    ready = LocalVLMStatus(state="ready", api_base="http://127.0.0.1:8081/v1", slots=2)
    monkeypatch.setattr(local_vlm, "manager", lambda: type("M", (), {"status": lambda self: ready})())
    providers.use_local_server("http://127.0.0.1:8081/v1")
    assert providers.resolve_model("llamacpp:local").max_parallel == 2
    providers.use_local_server("http://127.0.0.1:9999/v1")
    assert providers.resolve_model("llamacpp:local").max_parallel is None


def test_a_local_server_address_left_from_last_time_must_answer_now(monkeypatch):
    providers.use_local_server("http://127.0.0.1:8081/v1")       # where TwinStore's model ran last time
    monkeypatch.setattr(local_vlm, "manager", lambda: _LocalModel(["off"]))
    answering: list[str] = []
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: (answering.append(base), bool(answering[1:]))[1])
    config = LLMConfig(model="anthropic/claude-haiku-5-5")
    assert providers.assistive_model("", config) == "anthropic/claude-haiku-5-5"   # nothing answers there now
    assert providers.assistive_model("", config) == "llamacpp:local"              # a server answers (the user's own)
    assert answering == ["http://127.0.0.1:8081/v1"] * 2
    monkeypatch.setattr(local_vlm, "manager", lambda: _LocalModel(["downloading"]))
    assert providers.assistive_model("", config) == "anthropic/claude-haiku-5-5"   # TwinStore's own is on its way


def test_with_no_usable_key_anywhere_no_request_is_sent_to_a_provider(monkeypatch, fake_calls):
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: False)
    monkeypatch.setattr(local_vlm, "manager", lambda: _LocalModel(["downloading"]))
    with pytest.raises(ValueError, match=r"No API key for Anthropic \(Claude\)\. The local model .* getting ready"):
        providers.assistive_client("", LLMConfig(model="anthropic/claude-haiku-5-5"))
    assert fake_calls.models == []
    # A background job waits and starts on the local model.
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    local = _LocalModel(["downloading", "starting", "ready"])
    monkeypatch.setattr(local_vlm, "manager", lambda: local)
    client = providers.assistive_client("", LLMConfig(model="anthropic/claude-haiku-5-5"), wait=600)
    assert client.model == "openai/local-model" and asyncio.run(client.generate_structured_async(_Answer, "s", "u"))
    assert fake_calls.models == ["openai/local-model"]
    # A model on an endpoint of the app configuration is used as it is.
    own = LLMConfig(model="openai/served-model", api_base="http://127.0.0.1:9000/v1")
    assert providers.assistive_client("", own).model == "openai/served-model"


def test_generated_customers_carry_only_what_the_prompt_asks_for():
    from store_emulator.engine.generators import persona as gen

    schema = gen.PersonaBatch.model_json_schema()
    fields = set(schema["$defs"]["GeneratedPersona"]["properties"])
    assert fields == {"id", "identity", "age_group", "gender", "description", "intent", "purpose",
                      "preferred_categories", "budget_min", "budget_max", "behavior_tendency"}
    assert schema["$defs"]["GeneratedPersona"]["properties"]["description"]["maxLength"] == 600
    generated = gen.GeneratedPersona(identity="student", age_group="20s", gender="Female", description="d",
                                     intent="i", purpose="p", preferred_categories=["snacks"], budget_max=500)
    persona = gen.Persona.model_validate(generated.model_dump())
    assert persona.category_rates == {} and persona.basket_size == 0 and persona.preferred_categories == ["snacks"]


def test_the_wait_note_is_cleared_once_the_local_model_answers(monkeypatch):
    from store_emulator.application import generation_async
    from store_emulator.domain.config import SimulationConfig

    class _Client:
        max_parallel = 1
        model = "openai/local-model"

        def get_usage(self):
            from store_emulator.domain.types import TokenUsage
            return TokenUsage()

    def client(requested, config, *, wait, on_wait):
        on_wait("waiting for the local model: Downloading (40%)")
        return _Client()

    async def batched(*a, **k):
        return ["a customer"]

    writes: list[object] = []
    monkeypatch.setattr(generation_async, "assistive_client", client)
    monkeypatch.setattr(generation_async.gen_persona, "generate_batched", batched)
    monkeypatch.setattr(generation_async, "write_status", lambda *a, **k: writes.append(k["progress"]))
    asyncio.run(generation_async._run_async_pipeline(  # pyright: ignore[reportPrivateUsage]
        config=SimulationConfig(), project_id="p", meta={}, schedules=[], custom_instruction="",
        supplemental_bytes=None, supplemental_filename="", gen_id="g"))
    assert writes == [{"note": "waiting for the local model: Downloading (40%)"}, {}]


def test_most_customer_requests_failing_fails_generation_with_a_plain_reason(monkeypatch):
    from store_emulator.application import generation_async
    from store_emulator.domain.store import DaySchedule
    from store_emulator.engine.generators import persona as gen

    async def analyze_location(*a, **k):
        return gen.TradeAreaProfile(keywords=["k"], identities=["student"], purposes=["snack"])

    async def analyze_daily_traffic(*a, **k):
        return [gen.HourlyProfile(hour=h, visitor_count=10, person_types=["student"]) for h in range(8, 18)]

    calls = [0]
    in_flight, peak = [0], [0]

    class _LLM:
        async def generate_structured_async(self, model, system, user, **k):
            calls[0] += 1
            n = calls[0]
            in_flight[0] += 1
            peak[0] = max(peak[0], in_flight[0])
            await asyncio.sleep(0)
            in_flight[0] -= 1
            if n % 4:                   # three of every four requests are refused
                raise litellm.RateLimitError("Too many requests", llm_provider="anthropic", model="m")
            return gen.PersonaBatch(personas=[])

    monkeypatch.setattr(gen, "analyze_location", analyze_location)
    monkeypatch.setattr(gen, "analyze_daily_traffic", analyze_daily_traffic)
    week = [DaySchedule(day=d, is_open=True, open_hour=8, close_hour=18) for d in range(1, 8)]
    with pytest.raises(gen.TooManyBatchesFailed) as failed:
        asyncio.run(gen.generate_batched(_LLM(), "addr", "profile", week))  # type: ignore[arg-type]
    assert failed.value.tally.requested == 70 and failed.value.tally.failed > 35
    assert peak[0] <= 20                 # one limit for the whole week, not 10 a day
    text = generation_async._failure_text(failed.value)  # pyright: ignore[reportPrivateUsage]
    assert text.startswith("Customer generation failed (") and "requests to the model): the provider is limiting" in text
    assert generation_async._failure_text(ValueError("No API key for X")) == "No API key for X"  # pyright: ignore[reportPrivateUsage]


def test_the_default_vision_endpoint_follows_the_local_server_and_dead_ones_leave_the_pickers(monkeypatch):
    from store_emulator.application import capture
    from store_emulator.domain.config import SimulationConfig

    ready = LocalVLMStatus(state="ready", api_base="http://127.0.0.1:53303/v1", slots=1, managed=True)
    monkeypatch.setattr(local_vlm, "manager", lambda: type("M", (), {"status": lambda self: ready})())
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: base == "http://127.0.0.1:53303/v1")
    vision = SimulationConfig().engines.vlm_glance.llm          # openai/local-vlm at 127.0.0.1:8081
    resolved = providers.resolve_model(vision.model, base=vision)
    assert resolved.api_base == "http://127.0.0.1:53303/v1" and resolved.max_parallel == 1
    own = vision.model_copy(update={"api_base": "http://gpu-box:8081/v1"})
    assert providers.resolve_model(own.model, base=own).api_base == "http://gpu-box:8081/v1"
    captured = capture.capture_llm_config(SimulationConfig(), "")
    assert captured is not None and captured.api_base == "http://127.0.0.1:53303/v1" and captured.max_parallel == 1

    # A llama.cpp server that is not up is not offered in model pickers.
    providers.use_local_server("http://127.0.0.1:8081/v1")
    stopped = LocalVLMStatus(state="off")
    monkeypatch.setattr(local_vlm, "manager", lambda: type("M", (), {"status": lambda self: stopped})())
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: False)
    assert not any(m["ref"] == "llamacpp:local" for m in providers.available_models())
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: True)
    assert any(m["ref"] == "llamacpp:local" for m in providers.available_models())


def test_the_uploaded_customer_data_is_kept_until_its_summary_is_made(tmp_path, monkeypatch):
    from store_emulator.application import generation_async
    from store_emulator.application.storage.io import write_json
    from store_emulator.application.storage.setups import metadata_path

    monkeypatch.chdir(tmp_path)
    write_json(metadata_path("proj_up"), {"supplemental_summary": ""})
    generation_async._keep_upload("proj_up", b"day,hour\n1,9\n", "고객 데이터.CSV")  # pyright: ignore[reportPrivateUsage]
    assert generation_async._kept_upload("proj_up") == (b"day,hour\n1,9\n", "고객 데이터.CSV")  # pyright: ignore[reportPrivateUsage]
    assert (metadata_path("proj_up").parent / "supplemental" / "upload.csv").is_file()
    write_json(metadata_path("proj_up"), {"supplemental_summary": "students at lunch"})
    assert generation_async._kept_upload("proj_up") is None  # pyright: ignore[reportPrivateUsage]

    # "Try again" without a file picks the kept one up.
    write_json(metadata_path("proj_up"), {"supplemental_summary": ""})
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(generation_async, "read_setup", lambda pid, sid: {"id": sid})
    monkeypatch.setattr(generation_async, "find_active_generation", lambda *a, **k: None)
    monkeypatch.setattr(generation_async, "init_generation", lambda *a: "gen_1")
    monkeypatch.setattr(generation_async.executor, "submit", lambda fn, *a, **k: submitted.append(k))
    from store_emulator.application.storage import setups as setup_store
    monkeypatch.setattr(setup_store, "list_setups", lambda pid: [])
    from store_emulator.domain.config import SimulationConfig
    generation_async.start_persona_generation(SimulationConfig(), "proj_up", "setup_1")
    assert submitted[0]["supplemental_bytes"] == b"day,hour\n1,9\n" and submitted[0]["supplemental_filename"] == "고객 데이터.CSV"


def test_trying_again_restarts_a_local_model_that_failed(monkeypatch, fake_calls):
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "1")
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: False)
    local = _LocalModel(["error", "error", "preparing", "downloading", "ready"])
    monkeypatch.setattr(local_vlm, "manager", lambda: local)
    client = providers.assistive_client("", LLMConfig(model="anthropic/claude-haiku-5-5"), wait=600)
    assert client.model == "openai/local-model" and local.started == 1
