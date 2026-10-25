"""Repeated respondent text must not crowd statistics and caveats out of report commentary."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application import marketing, study_reading
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.marketing import JobStatus, SurveyAnswer, SurveyRequest
from store_emulator.domain.persona import AGE_GROUPS, GENDERS
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.reading import MAX_REPORT_CHARS, compact_report


def complete_survey(currency, verbose):
    request = SurveyRequest(stimuli=["a", "b", "c", "d"], currency=currency,
        questions=["purchase_intent", "appeal", "value", "uniqueness", "price_vw", "preference", "open"])
    answers = [SurveyAnswer(respondent=f"p{i}", age_group=AGE_GROUPS[i % 6], gender=GENDERS[i // 6 % 2],
        purchase_intent=[1, 2, 3, 4], appeal=[2, 3, 4, 5], value=[3, 4, 5, 1], uniqueness=[4, 5, 1, 2],
        too_cheap=10 + i, cheap=100 + i, expensive=500 + i, too_expensive=900 + i, preferred=i % 4,
        why=("Fresh flavor and a familiar package. " * 8)[:240] if verbose else "Fresh flavor.") for i in range(48)]
    answers.append(SurveyAnswer(respondent="failed", age_group="20s", gender="Female", error="Timed out"))
    return marketing.summarize_survey("srv_context", "Four packs", "local", request, ["A", "B", "C", "D"], answers)


@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("verbose", [False, True])
def test_compact_report_preserves_all_aggregates_and_caveats(currency, verbose):
    report = complete_survey(currency, verbose)
    before, excluded = report.model_dump(), {"answers"}
    text = compact_report(report, excluded)
    expected_excluded = {"answers", "verbatims"} if verbose else {"answers"}
    assert json.loads(text) == report.model_dump(mode="json", exclude=expected_excluded)
    assert len(text) <= MAX_REPORT_CHARS and report.notes[-1] in text
    assert len(report.verbatims) == 40 and report.model_dump() == before and excluded == {"answers"}
    if verbose:
        assert len(report.model_dump_json(exclude=excluded)) > MAX_REPORT_CHARS


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_http_commentary_retains_caveats_and_codes_all_reasons_before_saving(monkeypatch, tmp_path, mode):
    monkeypatch.chdir(tmp_path)
    report = complete_survey("USD", True)
    pid, jid = "proj_context", report.survey_id
    write_json(metadata_path(pid), {"name": "Corner Store", "currency": "USD"})
    root = marketing._job_dir(pid, "survey", jid)
    write_json(root / "status.json", JobStatus(job_id=jid, kind="survey", status="completed").model_dump(mode="json"))
    write_json(root / "report.json", report.model_dump(mode="json"))
    saved_report = (root / "report.json").read_bytes()
    monkeypatch.setattr(study_reading, "assistive_model", lambda *args: "openai/report-context")

    def client_factory(model, config):
        return llm_client.LiteLLMClient(config.model_copy(update={"model": model,
            "api_base": "http://127.0.0.1:8081/v1", "structured_output": mode, "cache_dir": str(tmp_path / "cache")}))

    monkeypatch.setattr(study_reading, "assistive_client", client_factory)
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        user = next(message["content"] for message in body["messages"] if message["role"] == "user")
        if "Answers:\n" in user:
            answers = user.split("Answers:\n", 1)[1].splitlines()
            assert len(answers) == 48 and all("Fresh flavor" in answer for answer in answers)
            payload = {"themes": ["Fresh flavor"], "assignments": [0] * 48}
        else:
            data = json.loads(user.split("Report:\n", 1)[1].split("\n\n", 1)[0])
            assert data == report.model_dump(mode="json", exclude={"answers", "verbatims"})
            assert data["respondents"] == 48 and data["errors"] == 1
            assert "Fresh flavor: 48 (100%)" in user
            payload = {"summary": "Synthetic responses favor different packs by question.",
                       "interpretation": "One failed respondent was excluded.", "next_steps": "Calibrate against a real panel."}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    for _ in range(2):
        result = study_reading.write_reading(pid, "survey", jid, "", SimulationConfig())
        assert result.answers_coded == 48 and result.themes[0].count == 48
        assert result.interpretation == "One failed respondent was excluded."
        assert read_json(root / "reading.json")["next_steps"] == "Calibrate against a real panel."
        assert (root / "report.json").read_bytes() == saved_report
        assert len(calls) == 2
