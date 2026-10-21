"""Survey exports preserve zero values independently of missing answers."""

import csv
import io

from fastapi.testclient import TestClient

from store_emulator.application import marketing
from store_emulator.domain.marketing import SurveyAnswer, SurveyReport
from store_emulator.server.main import app


def test_csv_distinguishes_zero_price_answers_from_missing_prices(monkeypatch):
    fields = ("too_cheap", "cheap", "expensive", "too_expensive")
    report = SurveyReport(
        survey_id="survey_test", name="Test", model="fake", stimuli=["asset_test"], stimulus_names=["Test"],
        questions=["price_vw"], currency="USD", respondents=2, errors=0,
        answers=[
            SurveyAnswer(respondent="zero", age_group="20s", gender="Female",
                         too_cheap=0, cheap=0, expensive=0, too_expensive=0),
            SurveyAnswer(respondent="missing", age_group="20s", gender="Female"),
        ],
    )
    view = marketing.SurveyView(job_id="survey_test", kind="survey", status="completed", report=report)
    monkeypatch.setattr(marketing, "get_survey", lambda *_args: view)

    response = TestClient(app).get("/api/projects/proj_test/surveys/survey_test/export.csv")

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [rows[0][field] for field in fields] == ["0"] * 4
    assert [rows[1][field] for field in fields] == [""] * 4
