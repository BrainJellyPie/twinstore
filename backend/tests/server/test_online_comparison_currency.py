"""A paired online run requires comparable budgets and monetary results."""

import pytest

from store_emulator.application import online
from tests.server.test_online_api import PID, client


@pytest.mark.parametrize("first,second", [("USD", "KRW"), ("KRW", "USD"), ("USD", "JPY"), ("JPY", "USD"),
                                        ("USD", "USD"), ("KRW", "KRW"), ("JPY", "JPY")])
def test_currency_mismatch_is_rejected_before_job_registration(client, monkeypatch, first, second):
    submitted = []
    monkeypatch.setattr(online, "submit_background", lambda *args, **kwargs: submitted.append(args))
    sites = []
    for currency in (first, second):
        layout = client.post(f"/api/projects/{PID}/setups/generate",
                             json={"template_id": "specialty_cafe", "currency": currency})
        assert layout.status_code == 200
        created = client.post(f"/api/projects/{PID}/online/sites",
                              json={"template_id": "from_store", "setup_id": layout.json()["id"]})
        assert created.status_code == 200
        site = created.json()
        assert site["currency"] == currency
        sites.append(site)
    response = client.post(f"/api/projects/{PID}/online/runs",
                           json={"site_ids": [site["id"] for site in sites], "shoppers": 1, "max_steps": 3})
    if first != second:
        assert response.status_code == 400 and "same currency" in response.text
        assert submitted == [] and client.get(f"/api/projects/{PID}/online/runs").json() == []
    else:
        assert response.status_code == 200 and len(submitted) == 1
    assert [client.get(f"/api/projects/{PID}/online/sites/{site['id']}").json() for site in sites] == sites
