"""A model's reading of finished studies: open answers coded into themes (per arm for paired studies) and a
commentary, kept with the study and shown in its report. Fake model, no network."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from store_emulator.application.storage.io import write_json
from store_emulator.domain.marketing import (
    JobStatus,
    ShelfChoice,
    ShelfTestReport,
    SurveyAnswer,
    SurveyReport,
)

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Analyst:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.prompts.append((response_model.__name__, system_prompt, user_prompt))
        if response_model.__name__ == "ThemeCoding":
            answers = [line.split(". ", 1)[1] for line in user_prompt.split("Answers:\n", 1)[1].splitlines()]
            return response_model.model_validate({"themes": ["Bright new pack", "Usual brand"],
                                                  "assignments": [0 if "pack" in a else 1 for a in answers]})
        return response_model.model_validate({"summary": "The new pack lifts picks.", "interpretation": "People notice it.",
                                              "next_steps": "Test the price next."})


def _job(tmp_path, folder: str, kind: str, jid: str, report: BaseModel) -> None:
    base = tmp_path / ".data" / PID / "marketing" / folder / jid
    write_json(base / "status.json", JobStatus(job_id=jid, kind=kind, status="completed").model_dump(mode="json"))  # type: ignore[arg-type]
    write_json(base / "report.json", report.model_dump(mode="json"))


def _shelf(tmp_path) -> None:
    why = {"control": ["I always buy my usual brand.", "My usual one.", "The pack caught my eye."],
           "test": ["The bright new pack caught my eye.", "Loved the new pack.", "New pack looked fresh.", "Usual brand."]}
    choices = [ShelfChoice(respondent=f"p{i}", age_group="30s", gender="F", arm=arm, why=w)  # type: ignore[arg-type]
               for arm, ws in why.items() for i, w in enumerate(ws)]
    choices.append(ShelfChoice(respondent="px", age_group="30s", gender="F", arm="test", error="timeout"))
    report = ShelfTestReport(test_id="slf_1", name="Pack test", setup_id="s", rack_id="r", rack_name="Drinks", face="N",
                             target_sku="A1", target_name="Leafy Tea", model="m", currency="USD", respondents=4, errors=1,
                             choices=choices)
    _job(tmp_path, "shelf_tests", "shelf", "slf_1", report)


def test_a_shelf_reading_codes_reasons_per_arm_and_writes_a_commentary(client, monkeypatch, tmp_path):
    from store_emulator.application import study_reading
    _shelf(tmp_path)
    fake = _Analyst()
    monkeypatch.setattr(study_reading, "assistive_client", lambda *a, **k: fake)
    url = f"/api/projects/{PID}/shelf-tests/slf_1/reading"
    assert client.get(url).status_code == 200 and client.get(url).json() is None
    assert client.get(f"/api/projects/{PID}/shelf-tests/slf_nope/reading").status_code == 404
    r = client.post(url, json={"model": "anthropic:claude-haiku-5-5"})
    assert r.status_code == 200, r.text
    reading = r.json()
    assert reading["summary"] == "The new pack lifts picks." and reading["model"] == "anthropic:claude-haiku-5-5"
    assert reading["answers_coded"] == 7 and reading["groups"] == ["control", "test"]
    pack, usual = reading["themes"]
    assert (pack["label"], pack["count"], pack["by_group"]) == ("Bright new pack", 4, {"control": 1, "test": 3})
    assert (usual["label"], usual["count"], usual["by_group"]) == ("Usual brand", 3, {"control": 2, "test": 1})
    assert pack["share"] == pytest.approx(4 / 7, abs=1e-4) and pack["examples"][0] == "Loved the new pack."
    themes_call, commentary_call = fake.prompts
    assert themes_call[0] == "ThemeCoding" and "Why did you take that product" in themes_call[2]
    # The commentary reads the report without respondent rows, plus the coded themes per arm.
    assert "virtual shelf test" in commentary_call[1] and '"choices"' not in commentary_call[2]
    assert '"target_name":"Leafy Tea"' in commentary_call[2] and "Bright new pack: 4 (57%); by arm control: 1, test: 3" in commentary_call[2]
    assert client.get(url).json() == reading
    assert client.delete(url).status_code == 204 and client.get(url).json() is None


def test_a_survey_reading_shows_in_the_report_and_skips_themes_for_few_answers(client, monkeypatch, tmp_path):
    from store_emulator.application import study_reading
    answers = [SurveyAnswer(respondent=f"p{i}", age_group="30s", gender="F", why=w) for i, w in enumerate(["Fresh.", "Cheap."])]
    _job(tmp_path, "surveys", "survey", "srv_1", SurveyReport(
        survey_id="srv_1", name="Tea concept", model="m", stimuli=["a"], stimulus_names=["Leafy"], questions=["open"],
        currency="USD", respondents=2, errors=0, answers=answers))
    fake = _Analyst()
    monkeypatch.setattr(study_reading, "assistive_client", lambda *a, **k: fake)
    reading = client.post(f"/api/projects/{PID}/surveys/srv_1/reading", json={}).json()
    assert reading["themes"] == [] and reading["answers_coded"] == 0 and reading["summary"]
    assert [p[0] for p in fake.prompts] == ["_Commentary"]
    page = client.get(f"/api/projects/{PID}/surveys/srv_1/report.html").text
    assert "Commentary and themes written by" in page and "The new pack lifts picks." in page


def test_reading_errors(client, monkeypatch, tmp_path):
    from store_emulator.application import study_reading

    class _Broken:
        async def generate_structured_async(self, *a, **k):
            raise TimeoutError("slow")

    write_json(tmp_path / ".data" / PID / "marketing" / "conjoints" / "cjt_1" / "status.json",
               JobStatus(job_id="cjt_1", kind="conjoint", status="running").model_dump(mode="json"))
    assert client.post(f"/api/projects/{PID}/conjoints/cjt_1/reading", json={}).status_code == 409
    assert client.post(f"/api/projects/{PID}/conjoints/nope/reading", json={}).status_code == 404
    assert client.post(f"/api/projects/{PID}/experiments/exp_1/reading", json={}).status_code == 422
    _shelf(tmp_path)
    monkeypatch.setattr(study_reading, "assistive_client", lambda *a, **k: _Broken())
    r = client.post(f"/api/projects/{PID}/shelf-tests/slf_1/reading", json={})
    assert r.status_code == 502 and "took too long" in r.json()["detail"]
    assert client.get(f"/api/projects/{PID}/shelf-tests/slf_1/reading").json() is None
