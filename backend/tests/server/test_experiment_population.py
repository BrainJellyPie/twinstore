"""Experiment reports must disclose the customers actually compared."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.optimize.evaluate import LayoutEvaluator


@pytest.mark.parametrize('empty', [False, True])
def test_experiment_reports_effective_population_or_failure(tmp_path, monkeypatch, empty):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TWINSTORE_LOCAL_VLM_AUTO', '0')
    panel = [Persona(id=f'p{i}', identity='Shopper', age_group='20s', gender='Female',
                     description='Tea', intent='tea', purpose='tea') for i in range(40)]
    monkeypatch.setattr(marketing, '_personas', lambda pid: panel)
    monkeypatch.setattr(marketing, 'executor', Mock(submit=lambda fn: fn()))
    calls = 0

    async def evaluate(self, store, personas):
        nonlocal calls
        calls += 1
        selected = panel if calls == 1 else ([] if empty else panel[:20])
        return [CustomerResult(persona_id=p.id, day=Weekday.MON, arrival_time='12:00:00', total_spent=100 * calls,
                               timeline=[TimelineEvent(elapsed_sec=1, x=1, y=1, action=Action.BUY,
                                                       target_rack='shelf', product_sku='A0017', product_name='Tea',
                                                       price=100 * calls)]) for p in selected]

    monkeypatch.setattr(LayoutEvaluator, 'evaluate_customers', evaluate)
    from store_emulator.server.main import app
    root = '/api/projects/proj_67916afd/experiments'
    with TestClient(app) as client:
        response = client.post(root, json={'setup_id':'setup_7d6d', 'panel':40, 'focus_skus':['A0017'],
                              'variants':[{'name':'Offer', 'changes':[{'kind':'promo','sku':'A0017','promo':'NEW'}]}]})
        assert response.status_code == 200, response.text
        job = response.json()['job_id']
        view = client.get(f'{root}/{job}').json()
        if empty:
            assert view['status'] == 'failed'
            assert view['report'] is None
            assert 'successful' in view['error'] or 'common' in view['error']
        else:
            assert view['status'] == 'completed', view['error']
            report = view['report']
            assert report['panel_size'] == 20
            assert report['control']['customers'] == 20
            assert report['variants'][0]['customers'] == 20
            assert any('40' in note and '20' in note for note in report['notes'])
            assert '20 shoppers per arm' in client.get(f'{root}/{job}/report.md').text
