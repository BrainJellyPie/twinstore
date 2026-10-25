"""The real layout-to-online API saves a product catalog, not shelf facings."""

import pytest

from tests.server.test_online_api import PID, client


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_generated_layout_import_has_one_row_per_source_sku(client, currency):
    layout = client.post(f"/api/projects/{PID}/setups/generate",
                         json={"template_id": "station_kiosk", "currency": currency})
    assert layout.status_code == 200
    saved = client.get(f"/api/projects/{PID}/setups/{layout.json()['id']}")
    assert saved.status_code == 200
    source = saved.json()
    expected = {item["sku"] for rack in source["store"]["racks"] for slot in rack["slots"] for item in slot["items"]}
    response = client.post(f"/api/projects/{PID}/online/sites",
                           json={"template_id": "from_store", "setup_id": source["id"]})
    assert response.status_code == 200
    site = response.json()
    assert len(site["products"]) == len(expected) and {p["sku"] for p in site["products"]} == expected
    assert client.get(f"/api/projects/{PID}/online/sites/{site['id']}").json() == site
    assert client.get(f"/api/projects/{PID}/online/sites").json()[0]["products"] == len(expected)
