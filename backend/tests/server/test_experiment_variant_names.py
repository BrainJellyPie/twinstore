from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from store_emulator.application import marketing
from store_emulator.application.errors import AppError
from store_emulator.domain.marketing import ExperimentRequest

@pytest.mark.parametrize('names', [['Offer','Offer'], ['Offer',' Offer '], ['Offer','offer'], ['Control'], [' control '], ['   '], ['\t\n']])
def test_invalid_variant_names_rejected_before_start(monkeypatch, names):
    from store_emulator.server.main import app
    start = Mock(side_effect=AppError('invalid variant names reached application', 418))
    monkeypatch.setattr(marketing, 'start_experiment', start)
    body = {'setup_id':'setup_test','variants':[{'name':name,'changes':[{'kind':'promo','sku':'tea','promo':'NEW'}]} for name in names]}
    response=TestClient(app).post('/api/projects/proj_test/experiments',json=body)
    assert response.status_code == 422, response.text
    start.assert_not_called()


def test_distinct_variant_names_are_trimmed_and_preserved():
    request=ExperimentRequest(setup_id='setup_test',variants=[{'name':name,'changes':[{'kind':'promo','sku':'tea','promo':'NEW'}]} for name in [' Tea offer ', 'Coffee offer']])
    assert [v.name for v in request.variants] == ['Tea offer','Coffee offer']
