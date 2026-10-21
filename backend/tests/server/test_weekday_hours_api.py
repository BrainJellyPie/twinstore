"""Weekday schedules survive portable buildings and reject invalid floors atomically."""
import pytest
from fastapi.testclient import TestClient
PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def hours(open_day=1):
    return [{"day": day, "is_open": day == open_day, "open_hour": 0 if day % 2 else 23, "close_hour": 24} for day in range(1, 8)]


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_six_floor_weekday_schedules_survive_preview_files_save_and_reuse(client, currency):
    floors = [{"label": f"Floor {index + 1}", "layout": {"template_id": "community_pharmacy", "currency": currency,
              "weekly_hours": list(reversed(hours(index + 1))), "close_hour": 8, "design_colors": {"floor": f"#{index:06x}"},
              "requirements": f"Preserve weekday {index + 1}"}} for index in range(6)]
    validated = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert validated.status_code == 200, validated.text
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Different weekdays", "floors": validated.json()["floors"]})
    assert created.status_code == 200, created.text
    for index, setup in enumerate(created.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        preview = client.post("/api/store-templates/preview", json=floors[index]["layout"])
        assert preview.status_code == 200, preview.text
        assert saved["store"]["weekly_schedule"] == saved["generation"]["weekly_hours"] == preview.json()["weekly_schedule"] == hours(index + 1)
        assert saved["store"]["design_colors"]["floor"] == f"#{index:06x}"
        portable = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": saved["generation"]})
        assert portable.status_code == 200, portable.text
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**portable.json()["layout"], "source_setup_id": setup["id"]})
        assert reused.status_code == 200, reused.text
        again = client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()
        assert again["store"]["weekly_schedule"] == hours(index + 1)
        assert again["store"]["racks"] == saved["store"]["racks"]
        assert again["generation"]["requirements"] == f"Preserve weekday {index + 1}"


@pytest.mark.parametrize("kind", ["missing", "duplicate", "closed", "overnight", "fraction", "bool", "extra", "empty"])
def test_invalid_weekly_hours_reject_import_and_save_without_partial_buildings(client, kind):
    good = {"template_id": "urban_cvs"}
    assert client.post(f"/api/projects/{PID}/setups/generate", json=good).status_code == 200
    before = client.get(f"/api/projects/{PID}/setups").json()
    entries = hours()
    if kind == "missing": entries.pop()
    elif kind == "duplicate": entries[-1]["day"] = 1
    elif kind == "closed": entries[0]["is_open"] = False
    elif kind == "overnight": entries[0].update(open_hour=23, close_hour=1)
    elif kind == "fraction": entries[0]["open_hour"] = 1.5
    elif kind == "bool": entries[0]["day"] = True
    elif kind == "extra": entries.append(entries[0])
    else: entries = []
    bad = {**good, "weekly_hours": entries}
    floors = [{"label": "Ground", "layout": good}, {"label": "Upper", "layout": bad}]
    for endpoint, payload in [
        ("/api/store-templates/preview", bad), (f"/api/projects/{PID}/setups/generate", bad),
        ("/api/store-templates/preset/validate", {"format": "twinstore-layout-options", "version": 1, "layout": bad}),
        ("/api/store-templates/building-preset/validate", {"format": "twinstore-building-options", "version": 1, "floors": floors}),
        (f"/api/projects/{PID}/setups/generate-building", {"name": "Invalid hours", "floors": floors}),
    ]:
        response = client.post(endpoint, json=payload)
        assert response.status_code == 422, response.text
        assert "weekly_hours" in response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
