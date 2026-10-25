"""The real browse endpoint preserves a visitor's choice through JSON requests."""

import pytest

from tests.server.test_online_api import PID, client  # noqa: F401


@pytest.mark.parametrize("device", ["desktop", "mobile"])
def test_large_default_can_be_disabled_and_reenabled_through_browse(client, device):
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "senior_care"}).json()
    url = f"/api/projects/{PID}/online/sites/{site['id']}/browse"
    page = client.post(url, json={"device": device}).json()
    for kind in ("open_settings", "toggle_large_text", "home", "open_settings"):
        option = next(o for o in page["options"] if o["kind"] == kind)
        response = client.post(url, json={"state": page["state"], "option": option["number"]})
        assert response.status_code == 200
        page = response.json()
    assert page["state"]["large_text"] is False
    toggle = next(o for o in page["options"] if o["kind"] == "toggle_large_text")
    assert toggle["label"] == "Use large text"
    page = client.post(url, json={"state": page["state"], "option": toggle["number"]}).json()
    assert page["state"]["large_text"] is True
    assert next(o for o in page["options"] if o["kind"] == "toggle_large_text")["label"] == "Use normal text"
