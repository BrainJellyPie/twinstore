"""Large valid studies retain every statistic and caveat in the model's input."""

import asyncio
import json
import random

import httpx
import pytest
from pydantic import BaseModel

from store_emulator.application import marketing
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ConjointRequest, ConjointRespondent, ConjointTask
from store_emulator.domain.persona import AGE_GROUPS, GENDERS
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.conjoint import design, estimate
from store_emulator.engine.marketing.reading import MAX_REPORT_CHARS, compact_report, read_study


@pytest.fixture
def report(monkeypatch):
    attrs = [{"name": f"{i}" + ("Long attribute name " * 3)[:39],
              "levels": [f"{j}" + ("Long level wording " * 4)[:59] for j in range(6)]} for i in range(6)]
    request = ConjointRequest(product=("Described product " * 9)[:160], name="Long research title " * 4,
        attributes=attrs, prices=[100, 200, 300, 400, 500, 600], panel=120, tasks=3)
    rng = random.Random(1)
    people = [ConjointRespondent(respondent=f"p{i}", age_group=AGE_GROUPS[i % 6], gender=GENDERS[i % 2],
        tasks=[ConjointTask(profiles=ps, choice=rng.choice([0, 1, 2, None])) for ps in design([6] * 7, 3, 3, rng)])
        for i in range(120)]
    # Real fitting and demographic aggregation; one bootstrap draw keeps this context test focused.
    monkeypatch.setattr(marketing, "estimate", lambda *args, **kwargs: estimate(*args, **kwargs, draws=1))
    return marketing.summarize_conjoint("c", request.name, "ollama_chat/model-with-a-long-name", request, people)


def restore_tables(value):
    if isinstance(value, dict):
        if set(value) == {"columns", "rows"}:
            return [dict(zip(value["columns"], row, strict=True)) for row in value["rows"]]
        return {key: restore_tables(item) for key, item in value.items()}
    return value


def test_maximum_valid_design_preserves_complete_json_statistics_and_notes(report):
    before, exclude = report.model_dump(), {"answers"}
    expected = report.model_dump(mode="json", exclude={"answers", "verbatims"})
    assert len(json.dumps(expected, ensure_ascii=False, separators=(",", ":"))) > MAX_REPORT_CHARS
    text = compact_report(report, exclude)
    assert len(text) <= MAX_REPORT_CHARS
    assert restore_tables(json.loads(text)) == expected
    assert all(note in text for note in report.notes)
    assert report.model_dump() == before and exclude == {"answers"}


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_actual_sdk_commentary_sees_complete_large_report(monkeypatch, tmp_path, report, provider, mode):
    calls = []
    expected = report.model_dump(mode="json", exclude={"answers", "verbatims"})
    answer = {"summary": "The fitted choices are uncertain.", "interpretation": "Read all reported caveats.",
              "next_steps": "Check with real customers."}

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        assert restore_tables(json.loads(user.removeprefix("Report:\n"))) == expected
        assert "columns" in body["messages"][0]["content"] and "rows" in body["messages"][0]["content"]
        content = json.dumps(answer)
        if provider == "ollama":
            payload = {"model": "large-report", "done": True, "done_reason": "stop",
                       "message": {"role": "assistant", "content": content}, "prompt_eval_count": 10, "eval_count": 5}
        else:
            payload = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                       "choices": [{"index": 0, "finish_reason": "stop",
                                    "message": {"role": "assistant", "content": content}}]}
        return httpx.Response(200, request=request, json=payload)

    def send(self, request, *args, **kwargs): return response(request)
    async def asend(self, request, *args, **kwargs): return response(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model=f"{'ollama_chat' if provider == 'ollama' else 'openai'}/large-report",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))
    text = compact_report(report, {"answers"})
    for _ in range(2):
        reading = asyncio.run(read_study(client, "conjoint study", text, "Why?", []))
        assert reading.summary == answer["summary"] and len(calls) == 1


def test_single_oversized_value_is_not_silently_cut_into_invalid_json():
    class ImportedReport(BaseModel):
        name: str
        notes: list[str]
    report = ImportedReport(name="Imported label " * 1500, notes=["The study has no usable answers."])
    assert json.loads(compact_report(report, set())) == report.model_dump(mode="json")
