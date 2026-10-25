"""Run estimates can distinguish stores with a possible reminder visit."""

from tests.server.test_online_api import PID, client  # noqa: F401


def test_list_reports_saved_and_copied_reminder_options(client):
    base = f"/api/projects/{PID}/online/sites"
    site = client.post(base, json={"template_id": "fashion"}).json()
    assert client.get(base).json()[0]["cart_reminder"] is False
    enabled = {**site, "options": {**site["options"], "cart_reminder": True}}
    assert client.put(f"{base}/{site['id']}", json=enabled).status_code == 200
    copy = client.post(f"{base}/{site['id']}/copy", json={
        "options": {**site["options"], "cart_reminder": False},
    }).json()
    listed = {row["id"]: row for row in client.get(base).json()}
    assert listed[site["id"]]["cart_reminder"] is True
    assert listed[copy["id"]]["cart_reminder"] is False
