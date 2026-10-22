"""Photo and vision features check their model before starting, and say so when it cannot answer."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm, providers
from store_emulator.application.errors import AppError, job_failure
from store_emulator.application.local_vlm import LocalVLMStatus
from store_emulator.domain.config import LLMConfig, SimulationConfig

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PARASTORE_SETTINGS_DIR", str(tmp_path / "settings"))
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "DASHSCOPE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: False)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_shelf_capture_refuses_a_local_model_that_is_not_running_and_uses_a_cloud_key(client, monkeypatch):
    from store_emulator.application import capture

    with pytest.raises(AppError) as refused:
        capture.capture_llm_config(SimulationConfig(), "")
    assert refused.value.status_code == 503 and "No model server answers at http://127.0.0.1:8081/v1" in refused.value.message
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")                 # a key, and the local model off
    monkeypatch.setattr(local_vlm, "manager", lambda: type("M", (), {"status": lambda self: LocalVLMStatus(state="off")})())
    cfg = capture.capture_llm_config(SimulationConfig(), "")
    assert cfg is not None and cfg.model == "openai/gpt-6-luna" and cfg.api_base is None


def test_a_vision_ab_test_on_a_model_that_cannot_answer_is_refused(client):
    body = {"setup_id": "setup_7d6d", "engine": "vlm", "panel": 20,
            "variants": [{"name": "Half price", "changes": [{"kind": "discount", "sku": "A0017", "percent": -50}]}]}
    r = client.post(f"/api/projects/{PID}/experiments", json=body)
    assert r.status_code == 400 and "No model server answers" in r.json()["detail"]


def test_a_concept_test_nobody_answered_fails_instead_of_reporting_zeros():
    from store_emulator.application import marketing
    from store_emulator.domain.marketing import SurveyAnswer, SurveyRequest

    req = SurveyRequest(stimuli=["img_a"], questions=["purchase_intent"])
    answers = [SurveyAnswer(respondent=f"p{i}", age_group="20s", gender="Female", error="APIConnectionError: Connection error.")
               for i in range(3)]
    with pytest.raises(ValueError, match="No respondent could answer.*Connection error"):
        marketing.summarize_survey("s1", "test", "m", req, ["A"], answers)


def test_job_failures_read_as_advice():
    assert job_failure(ValueError("No shoppers come"), "x") == "No shoppers come"
    text = job_failure(RuntimeError("APIConnectionError: Connection error."), "Reading the shelf photo failed")
    assert text.startswith("Reading the shelf photo failed: the model could not be reached")


def test_assistive_answers_name_the_model_that_answered(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    client = providers.assistive_client("", LLMConfig(model="anthropic/claude-haiku-5-5"))
    assert providers.answered_by(client, "anthropic:claude-haiku-5-5") == "anthropic/claude-haiku-5-5"
    fallback = providers._FALLBACKS[client]  # pyright: ignore[reportPrivateUsage]
    fallback.ref = "llamacpp:local"           # it moved on after the key was turned down
    assert providers.answered_by(client, "anthropic:claude-haiku-5-5") == "llamacpp:local"
    assert providers.answered_by(object(), "x") == "x"


def test_marketing_csv_exports_open_in_excel():
    import inspect

    from store_emulator.server.routes import marketing as routes
    assert inspect.getsource(routes).count('"\\ufeff" + text') == 4
