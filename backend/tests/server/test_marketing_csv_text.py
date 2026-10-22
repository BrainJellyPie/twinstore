"""Spreadsheet exports distinguish text from formulas without changing numeric or missing values."""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing
from store_emulator.domain.marketing import (
    ConjointAttribute, ConjointReport, ConjointRespondent, ConjointTask, SurveyAnswer, SurveyReport,
)
from store_emulator.server.main import app

TEXT_CASES = [
    ('=1+1', "'=1+1"), ('+1+1', "'+1+1"), ('-1+1', "'-1+1"), ('@SUM(1,2)', "'@SUM(1,2)"),
    (' \t=1+1', "' \t=1+1"), ('\r\n+1+1', "'\r\n+1+1"), ('-20% sugar', "'-20% sugar"),
    ('Regular', 'Regular'), ('Tea, "large"', 'Tea, "large"'), ('Zero\nsugar', 'Zero\nsugar'),
    ("'=1+1", "'=1+1"), ('0', '0'),
]


@pytest.mark.parametrize("text,expected", TEXT_CASES)
@pytest.mark.parametrize("none_option", [False, True])
@pytest.mark.parametrize("has_price", [False, True])
def test_conjoint_csv_preserves_text_headers_options_and_none_rows(monkeypatch, text, expected, none_option, has_price):
    attrs = [ConjointAttribute(name=text, levels=[text, 'Plain']), ConjointAttribute(name='Pack', levels=['Can', 'Bottle'])]
    profiles = [[0, 0, 0], [1, 1, 1]] if has_price else [[0, 0], [1, 1]]
    report = ConjointReport(
        conjoint_id='cjt_test', name='Test', model='fake', product='tea', currency='USD', attributes=attrs,
        prices=[0, 200] if has_price else [], options=2, none_option=none_option, respondents=1, errors=1,
        answers=[
            ConjointRespondent(respondent=text, age_group=text, gender=text, tasks=[
                ConjointTask(profiles=profiles, choice=0), ConjointTask(profiles=profiles, choice=None if none_option else 1),
            ]),
            ConjointRespondent(respondent='failed', age_group='20s', gender='F', error='timeout', tasks=[ConjointTask(profiles=profiles)]),
        ],
    )
    before = report.model_dump()
    view = marketing.ConjointView(job_id='cjt_test', kind='conjoint', status='completed', report=report)
    monkeypatch.setattr(marketing, 'get_conjoint', lambda *_: view)
    response = TestClient(app).get('/api/projects/proj_test/conjoints/cjt_test/export.csv')
    assert response.status_code == 200
    assert response.text.startswith("\ufeff")   # opens as UTF-8 in Excel
    rows = list(csv.reader(io.StringIO(response.text.removeprefix("\ufeff"))))
    # Attribute labels are stripped by the request model; persona fields retain their original whitespace.
    label = expected if text == text.strip() else "'" + text.strip()
    header = ['respondent', 'age_group', 'gender', 'task', 'option', label, 'Pack', *(['price'] if has_price else []), 'chosen']
    assert rows[0] == header
    assert len(rows) == 1 + 2 * (2 + int(none_option))
    assert all(len(row) == len(header) for row in rows)
    for row in rows[1:]:
        assert row[:3] == [expected] * 3
        assert row[3] in ('1', '2') and row[-1] in ('0', '1')
        if row[4] == 'A':
            assert row[5:7] == [label, 'Can']
            if has_price:
                assert row[7] == '0'
        elif row[4] == 'B':
            assert row[5:7] == ['Plain', 'Bottle']
            if has_price:
                assert row[7] == '200'
        else:
            assert row[4] == 'none' and row[5:-1] == [''] * (2 + int(has_price))
    for task in ('1', '2'):
        assert sum(int(row[-1]) for row in rows[1:] if row[3] == task) == 1
    assert report.model_dump() == before


@pytest.mark.parametrize("text,expected", TEXT_CASES)
def test_survey_csv_preserves_text_answers_and_numeric_zero(monkeypatch, text, expected):
    report = SurveyReport(
        survey_id='srv_test', name='Test', model='fake', stimuli=['asset_test'], stimulus_names=['Test'],
        questions=['purchase_intent', 'price_vw', 'preference', 'open'], currency='USD', respondents=2, errors=0,
        answers=[
            SurveyAnswer(respondent=text, age_group=text, gender=text, purchase_intent=[5], too_cheap=0, cheap=100,
                         expensive=200, too_expensive=300, preferred=0, why=text, error=text),
            SurveyAnswer(respondent='missing', age_group='20s', gender='F'),
        ],
    )
    before = report.model_dump()
    view = marketing.SurveyView(job_id='srv_test', kind='survey', status='completed', report=report)
    monkeypatch.setattr(marketing, 'get_survey', lambda *_: view)
    response = TestClient(app).get('/api/projects/proj_test/surveys/srv_test/export.csv')
    assert response.status_code == 200
    assert response.text.startswith("\ufeff")   # opens as UTF-8 in Excel
    rows = list(csv.DictReader(io.StringIO(response.text.removeprefix("\ufeff"))))
    for field in ('respondent', 'age_group', 'gender', 'why', 'error'):
        assert rows[0][field] == expected
    assert [rows[0][field] for field in ('purchase_intent_A', 'too_cheap', 'cheap', 'expensive', 'too_expensive', 'preferred')] == ['5', '0', '100', '200', '300', 'A']
    assert [rows[1][field] for field in ('purchase_intent_A', 'too_cheap', 'cheap', 'expensive', 'too_expensive', 'preferred', 'why', 'error')] == [''] * 8
    assert report.model_dump() == before
