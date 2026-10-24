"""Blank model commentary cannot overwrite a saved study reading or become a cached success."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application import marketing, study_reading
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.marketing import JobStatus
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.reading import StudyReading
from store_emulator.engine.marketing.report import ReportNarrative
from tests.engine.test_marketing_report_losses import losing_report


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["study", "experiment"])
@pytest.mark.parametrize("blank", ["", " \t\u3000\n"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_blank_summaries_are_corrected_before_cache_and_saved_reading(monkeypatch, tmp_path, mode, kind, blank, outcome):
    monkeypatch.chdir(tmp_path)
    pid, jid = "proj_summary", "study_summary"
    write_json(metadata_path(pid), {"name": "Corner Store", "currency": "USD"})
    module = study_reading if kind == "study" else marketing
    job_kind = "survey" if kind == "study" else "experiment"
    root = marketing._job_dir(pid, job_kind, jid)
    write_json(root / "status.json", JobStatus(job_id=jid, kind=job_kind, status="completed").model_dump(mode="json"))
    path = root / ("reading.json" if kind == "study" else "narrative.json")
    previous = {"summary": "Existing review", "interpretation": "Existing detail", "next_steps": "Existing next step"}
    write_json(path, previous)
    if kind == "study":
        monkeypatch.setattr(module, "_material", lambda *args: ('{"buyers": 10}', "Why?", []))
    else:
        monkeypatch.setattr(module, "_report_inputs", lambda *args: (losing_report(), "Corner Store", None))
    monkeypatch.setattr(module, "assistive_model", lambda *args: "openai/local-summary")
    cache = tmp_path / "cache"

    def client_factory(model, config):
        return llm_client.LiteLLMClient(config.model_copy(update={"model": model,
            "api_base": "http://127.0.0.1:8081/v1", "structured_output": mode, "cache_dir": str(cache)}))

    monkeypatch.setattr(module, "assistive_client", client_factory)
    original, calls = llm_client.litellm.acompletion, []
    phase = "prime" if outcome == "legacy_cache" else "invalid"

    def respond(request):
        body = json.loads(request.content)
        bad = phase == "invalid" and not (outcome == "corrected" and calls)
        calls.append(body)
        payload = {"summary": blank if bad else "  Sales were lower in the variant.  ", "interpretation": "", "next_steps": ""}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)

    def write():
        if kind == "study":
            return study_reading.write_reading(pid, "survey", jid, "", SimulationConfig())
        return marketing.write_experiment_narrative(pid, jid, "", SimulationConfig())

    if outcome == "legacy_cache":
        write()
        files = list(cache.rglob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        data["result"]["summary"] = blank
        files[0].write_text(json.dumps(data))
        phase = "invalid"
    if outcome != "corrected":
        saved = path.read_bytes()
        with pytest.raises(AppError) as caught:
            write()
        assert caught.value.status_code == 502 and path.read_bytes() == saved
        assert len(calls) == (3 if outcome == "legacy_cache" else 2)
        phase = "complete"
    result = write()
    assert result.summary == "Sales were lower in the variant."
    assert not result.interpretation and not result.next_steps
    assert read_json(path)["summary"] == result.summary
    before = len(calls)
    assert write().summary == result.summary and len(calls) == before
    assert all(json.loads(p.read_text())["result"]["summary"] == result.summary for p in cache.rglob("*.json"))
    if outcome == "corrected":
        assert len(calls) == 2


def test_existing_empty_saved_readings_still_load():
    assert StudyReading.model_validate({"summary": ""}).summary == ""
    assert ReportNarrative.model_validate({"summary": "", "interpretation": "", "next_steps": ""}).summary == ""
