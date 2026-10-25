"""Survey commentary must know the brief and price respondents were shown."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application import marketing, study_reading
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.marketing import JobStatus, SurveyAnswer, SurveyRequest
from store_emulator.engine import llm_client
from store_emulator.engine.prompting import display_price


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("price", [None, 0, 999])
@pytest.mark.parametrize("brief", ["", "A 500 ml caffeine-free tea for the evening. 저녁용 차."])
def test_saved_conditions_reach_http_commentary_without_changing_study_files(monkeypatch, tmp_path, mode, currency, price, brief):
    monkeypatch.chdir(tmp_path)
    request = SurveyRequest(stimuli=["tea"], questions=["value"], context=brief, reference_price=price, currency=currency)
    answers = [SurveyAnswer(respondent=f"p{i}", age_group="20s", gender="Female", value=[3 + i]) for i in range(2)]
    report = marketing.summarize_survey("srv_conditions", "Tea", "local", request, ["Tea"], answers)
    pid, jid = "proj_conditions", report.survey_id
    write_json(metadata_path(pid), {"name": "Corner Store", "currency": currency})
    root = marketing._job_dir(pid, "survey", jid)
    write_json(root / "status.json", JobStatus(job_id=jid, kind="survey", status="completed").model_dump(mode="json"))
    write_json(root / "report.json", report.model_dump(mode="json"))
    write_json(root / "request.json", request.model_dump(mode="json"))
    snapshots = {name: (root / name).read_bytes() for name in ("status.json", "report.json", "request.json")}
    monkeypatch.setattr(study_reading, "assistive_model", lambda *args: "openai/survey-conditions")

    def client_factory(model, config):
        return llm_client.LiteLLMClient(config.model_copy(update={"model": model, "api_base": "http://127.0.0.1:8081/v1",
            "structured_output": mode, "cache_dir": str(tmp_path / "cache")}))

    monkeypatch.setattr(study_reading, "assistive_client", client_factory)
    original, calls = llm_client.litellm.acompletion, []

    def respond(http_request):
        body = json.loads(http_request.content)
        calls.append(body)
        payload = {"summary": "The synthetic panel rated this offer 3.5 on value.",
                   "interpretation": "The result depends on the stated study conditions.", "next_steps": "Confirm with real shoppers."}
        return httpx.Response(200, request=http_request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    expected_notes = list(report.notes)
    if brief:
        expected_notes.append(f"Respondent brief: {brief}")
    if price is not None:
        expected_notes.append(f"Reference price shown for product A: {display_price(price, currency)}.")
    for _ in range(2):
        reading = study_reading.write_reading(pid, "survey", jid, "", SimulationConfig())
        assert len(calls) == 1 and reading.answers_coded == 0
        user = calls[0]["messages"][1]["content"]
        data = json.loads(user.split("Report:\n", 1)[1].split("\n\n", 1)[0])
        assert data["notes"] == expected_notes
        assert data["scales"][0]["mean"] == 3.5 and data["respondents"] == 2
        assert {key: value for key, value in data.items() if key != "notes"} == report.model_dump(
            mode="json", exclude={"answers", "notes"})
        assert read_json(root / "reading.json")["summary"] == reading.summary
        assert snapshots == {name: (root / name).read_bytes() for name in snapshots}


def test_old_report_without_a_saved_request_does_not_invent_conditions(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    request = SurveyRequest(stimuli=["tea"], questions=["value"])
    report = marketing.summarize_survey("srv_legacy", "Tea", "local", request, ["Tea"],
        [SurveyAnswer(respondent="p", age_group="20s", gender="Female", value=[4])])
    pid = "proj_conditions"
    write_json(metadata_path(pid), {"name": "Corner Store"})
    root = marketing._job_dir(pid, "survey", report.survey_id)
    write_json(root / "status.json", JobStatus(job_id=report.survey_id, kind="survey", status="completed").model_dump(mode="json"))
    write_json(root / "report.json", report.model_dump(mode="json"))
    text, _, reasons = study_reading._material(pid, "survey", report.survey_id)
    assert json.loads(text) == report.model_dump(mode="json", exclude={"answers"}) and not reasons
