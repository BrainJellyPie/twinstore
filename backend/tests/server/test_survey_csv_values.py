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


def test_csv_names_the_currency_and_unit_of_price_answers(monkeypatch):
    def export(questions, currency):
        report = SurveyReport(
            survey_id="survey_test", name="Test", model="fake", stimuli=["asset_test"], stimulus_names=["Test"],
            questions=questions, currency=currency, respondents=1, errors=0,
            answers=[SurveyAnswer(respondent="r1", age_group="20s", gender="Female", purchase_intent=[4],
                                  too_cheap=900, cheap=1500, expensive=2500, too_expensive=3000)],
        )
        view = marketing.SurveyView(job_id="survey_test", kind="survey", status="completed", report=report)
        monkeypatch.setattr(marketing, "get_survey", lambda *_args: view)
        response = TestClient(app).get("/api/projects/proj_test/surveys/survey_test/export.csv")
        return list(csv.DictReader(io.StringIO(response.text.removeprefix("﻿"))))

    won = export(["price_vw"], "KRW")
    assert (won[0]["cheap"], won[0]["currency"], won[0]["minor_per_major"]) == ("1500", "KRW", "1")
    assert "currency" not in export(["purchase_intent"], "USD")[0]   # no prices, no unit columns
