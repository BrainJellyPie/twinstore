"""A price imported from an online variant must keep its original currency."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.async_executor import executor
from tests.server.test_store_currency import PID, client


def body(currency):
    request = {'setup_id': 'setup_eaf5', 'engine': 'rule', 'panel': 20, 'variants': [
        {'name': 'Imported price', 'changes': [{'kind': 'price', 'sku': 'A0001', 'price': 3000}]}]}
    if currency is not None:
        request['currency'] = currency
    return request


@pytest.mark.parametrize('currency', ['KRW', 'JPY', 'EUR', 'krw'])
def test_cross_currency_price_starts_no_job_and_leaves_layout_intact(client: TestClient, monkeypatch, currency):
    submit = Mock()
    monkeypatch.setattr(executor, 'submit', submit)
    path = f'/api/projects/{PID}/setups/setup_eaf5'
    before = client.get(path).json()
    result = client.post(f'/api/projects/{PID}/experiments', json=body(currency))
    assert result.status_code == 422, result.text
    assert currency.upper() in result.json()['detail'] and 'USD' in result.json()['detail']
    submit.assert_not_called()
    assert client.get(path).json() == before
    assert client.get(f'/api/projects/{PID}/experiments').json() == []


@pytest.mark.parametrize('currency', ['USD', 'usd', '', None])
def test_matching_and_legacy_requests_keep_price_and_save_currency(client: TestClient, monkeypatch, currency):
    submit = Mock()
    monkeypatch.setattr(executor, 'submit', submit)
    result = client.post(f'/api/projects/{PID}/experiments', json=body(currency))
    assert result.status_code == 200, result.text
    submit.assert_called_once()
    saved = client.get(f"/api/projects/{PID}/experiments/{result.json()['job_id']}").json()['request']
    assert saved['currency'] == 'USD'
    assert saved['variants'][0]['changes'][0]['price'] == 3000
