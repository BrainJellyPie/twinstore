"""Even a short model run needs a model decision before it can be completed."""

import json

import httpx
import pytest
from instructor.core.exceptions import IncompleteOutputException

from store_emulator.application import online
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.online import OnlineRunRequest, OnlineRunStatus
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import ModelPolicy, RulePolicy
from store_emulator.engine.online.shoppers import sample_shoppers


def _job(tmp_path, monkeypatch, policy, kind, *, survey=False, count=1):
    monkeypatch.chdir(tmp_path)
    site = build_site("toy_store", site_id="short")
    site = site.model_copy(update={"options": site.options.model_copy(update={
        "welcome_popup": "none", "cookie_banner": False, "cart_reminder": False,
    })})
    shoppers = sample_shoppers(site, count, seed=1, missions={"purchase": 1.0}, mobile_share=0)
    request = OnlineRunRequest(site_ids=[site.id], shoppers=count, policy=kind, max_steps=3, exit_survey=survey)
    status = OnlineRunStatus(run_id="run_short", site_ids=[site.id], status="pending", total=count, request=request)
    online._run_job("project", status, [site], shoppers, policy, "local" if kind != "rule" else "", lambda _: None)
    view = online.get_run("project", status.run_id)
    assert view.status.finished_at
    return view, online._run_dir("project", status.run_id)


@pytest.mark.parametrize("kind", ["text", "vlm"])
@pytest.mark.parametrize("failure", ["offline", "invalid", "cutoff", "survey_only"])
def test_short_run_with_no_model_decision_fails_without_publishing_results(tmp_path, monkeypatch, kind, failure):
    class Model:
        calls = 0

        async def generate_structured_async(self, schema, system, user, *args, **kwargs):
            if "survey" in system and failure == "survey_only":
                return schema.model_validate({"satisfaction": 4, "ease": 4, "recommend": 4, "would_return": False})
            self.calls += 1
            if failure == "cutoff":
                raise IncompleteOutputException("output is incomplete")
            if failure == "invalid":
                return schema.model_validate({"option": "not a number"})
            raise ConnectionError("Connection refused")

        generate_structured_with_image_async = generate_structured_async

    policy = ModelPolicy(Model(), vision=kind == "vlm")
    view, folder = _job(tmp_path, monkeypatch, policy, kind, survey=failure == "survey_only")
    assert 0 < policy.failed <= 3 and policy.answered == 0
    assert view.status.status == "failed" and view.status.error
    assert view.result is None and not list(folder.glob("sessions-*.json"))
    expected = {"offline": "could not be reached", "survey_only": "could not be reached",
                "invalid": "validation error", "cutoff": "cut off"}[failure]
    assert expected in view.status.error.lower()


@pytest.mark.parametrize("kind", ["text", "vlm", "rule"])
def test_short_successful_model_and_rule_runs_still_finish(tmp_path, monkeypatch, kind):
    class Model:
        async def generate_structured_async(self, schema, system, user, *args, **kwargs):
            leave = next(line for line in user.splitlines() if "Close the tab" in line)
            return schema.model_validate({"option": int(leave[1:leave.index("]")]), "thought": "Not today."})

        generate_structured_with_image_async = generate_structured_async

    policy = RulePolicy() if kind == "rule" else ModelPolicy(Model(), vision=kind == "vlm")
    view, folder = _job(tmp_path, monkeypatch, policy, kind)
    assert view.status.status == "completed", view.status.error
    assert view.result is not None and list(folder.glob("sessions-*.json"))


@pytest.mark.parametrize("works_first", [False, True])
def test_one_answer_preserves_recovery_and_partial_fallback(tmp_path, monkeypatch, works_first):
    class Model:
        calls = 0

        async def generate_structured_async(self, schema, system, user, **kwargs):
            self.calls += 1
            if (self.calls == 1) != works_first:
                raise ConnectionError("Connection refused")
            leave = next(line for line in user.splitlines() if "Close the tab" in line)
            return schema.model_validate({"option": int(leave[1:leave.index("]")]), "thought": "Not today."})

    policy = ModelPolicy(Model(), vision=False)
    view, _ = _job(tmp_path, monkeypatch, policy, "text", count=2)
    assert policy.answered and policy.failed
    assert view.status.status == "completed", view.status.error
    assert view.result is not None and view.result.fallbacks > 0


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["text", "vlm"])
def test_actual_sdk_short_run_rejects_a_provider_that_never_answers(tmp_path, monkeypatch, provider, structured, kind):
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion", "vision"]})
        calls.append(json.loads(request.content))
        return httpx.Response(400, request=request, json={"error": {"type": "invalid_request_error",
                                                                    "message": "Unsupported local model request"}})

    def send(self, request, *args, **kwargs): return response(request)
    async def asend(self, request, *args, **kwargs): return response(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    cache = tmp_path / "cache"
    client = LiteLLMClient(LLMConfig(model="ollama_chat/short-test" if provider == "ollama" else "openai/short-test",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=structured, structured_sdk_retries=0, cache_dir=str(cache), seed=0))
    policy = ModelPolicy(client, vision=kind == "vlm")
    view, folder = _job(tmp_path, monkeypatch, policy, kind)
    assert 1 <= len(calls) == policy.failed <= 3 and policy.answered == 0
    assert view.status.status == "failed" and view.status.error and view.result is None
    assert not list(folder.glob("sessions-*.json")) and not list(cache.glob("*/*.json"))
