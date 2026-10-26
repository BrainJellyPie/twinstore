"""Unanswered exit surveys stay visible without becoming zero-score measurements."""
import json

import pytest

from store_emulator.application import online
from store_emulator.domain.online import OnlineRunRequest, OnlineRunStatus, SessionResult
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import ModelPolicy, RulePolicy
from store_emulator.engine.online.shoppers import sample_shoppers
from tests.server.test_online_short_model_failure import _job


class Model:
    def __init__(self, valid_surveys=0, first_choice_fails=False):
        self.valid_surveys = valid_surveys
        self.surveys = self.choices = 0
        self.first_choice_fails = first_choice_fails

    async def generate_structured_async(self, schema, system, user, *args, **kwargs):
        if 'satisfaction' in schema.model_fields:
            self.surveys += 1
            if self.surveys <= self.valid_surveys:
                return schema.model_validate({'satisfaction': 4, 'ease': 3, 'recommend': 0, 'would_return': False})
            # The actual CPU failure copies field definitions rather than scores.
            return schema.model_validate(schema.model_json_schema())
        self.choices += 1
        if self.first_choice_fails and self.choices == 1:
            raise ConnectionError('first choice unavailable')
        line = next(line for line in user.splitlines() if 'Close the tab' in line)
        return schema.model_validate({'option': int(line.split(']', 1)[0][1:])})

    generate_structured_with_image_async = generate_structured_async


@pytest.mark.parametrize('kind', ['text', 'vlm'])
@pytest.mark.parametrize('valid', [0, 1, 3])
def test_completed_report_counts_missing_surveys_and_keeps_valid_zero_recommendations(tmp_path, monkeypatch, kind, valid):
    model = Model(valid_surveys=valid)
    view, _ = _job(tmp_path, monkeypatch, ModelPolicy(model, vision=kind == 'vlm'), kind, survey=True, count=3)
    assert view.status.status == 'completed' and view.result is not None
    assert model.surveys == 3 and view.result.fallbacks == 0
    notes = [note for note in view.result.notes if 'Exit surveys' in note]
    if valid < 3:
        assert len(notes) == 1 and f'{3-valid} of 3 requested surveys' in notes[0]
    else:
        assert notes == []
    summary = view.result.variants[0].survey
    if valid:
        assert summary is not None and summary.responses == valid
        assert summary.satisfaction == 4 and summary.nps == -100 and summary.would_return == 0
    else:
        assert summary is None


@pytest.mark.parametrize('kind', ['text', 'vlm', 'rule'])
def test_no_missing_survey_warning_when_no_survey_was_requested_from_a_model(tmp_path, monkeypatch, kind):
    model = Model()
    policy = RulePolicy() if kind == 'rule' else ModelPolicy(model, vision=kind == 'vlm')
    view, _ = _job(tmp_path, monkeypatch, policy, kind, survey=kind == 'rule')
    assert view.status.status == 'completed' and view.result is not None
    assert model.surveys == 0
    assert not any('Exit surveys' in note for note in view.result.notes)


def test_failed_choices_are_counted_against_choices_not_survey_requests(tmp_path, monkeypatch):
    model = Model(first_choice_fails=True)
    view, folder = _job(tmp_path, monkeypatch, ModelPolicy(model, vision=False), 'text', survey=True, count=2)
    assert view.result is not None and view.status.status == 'completed'
    sessions = [SessionResult.model_validate(row) for row in json.loads((folder/'sessions-0.json').read_text())]
    decisions = sum(step.choice is not None and step.source in {'model', 'fallback'} for s in sessions for step in s.steps)
    assert view.result.fallbacks == 1 and model.surveys == 2
    assert any(f'1 of {decisions} model decisions failed' in note for note in view.result.notes)
    assert view.result.model_requests == decisions + 2


def test_coverage_is_reported_per_variant_and_excludes_the_rival_without_a_survey(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sites = [build_site('toy_store', site_id=key, name=key) for key in ['Alpha', 'Beta', 'Rival']]
    for site in sites:
        site.options.welcome_popup = 'none'
        site.options.cookie_banner = False
        site.options.cart_reminder = False
    shoppers = sample_shoppers(sites[0], 1, seed=1, missions={'purchase': 1.0}, mobile_share=0)
    monkeypatch.setattr(online, 'tries_rival', lambda *args: True)
    model = Model()
    policy = ModelPolicy(model, vision=False)
    request = OnlineRunRequest(site_ids=['Alpha', 'Beta'], rival_site_id='Rival', policy='text', shoppers=1,
        exit_survey=True, max_steps=3)
    status = OnlineRunStatus(run_id='run_coverage', site_ids=request.site_ids, status='pending', total=3, request=request)
    online._run_job('project', status, sites[:2], shoppers, policy, 'local', lambda _: None, sites[2])
    view = online.get_run('project', status.run_id)
    assert view.status.status == 'completed' and view.result is not None
    assert model.surveys == 2 and model.choices == 3
    notes = [note for note in view.result.notes if 'Exit surveys' in note]
    assert len(notes) == 2
    assert all('1 of 1 requested surveys' in note for note in notes)
    assert any('Alpha' in note for note in notes) and any('Beta' in note for note in notes)
    assert all('Rival' not in note for note in notes)
