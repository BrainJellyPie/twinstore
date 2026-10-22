"""A scenario's preview shows the effect sizes a run of that layout uses (its store format), not the convenience
store's for every layout."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import read_setup, setup_path

PID, SETUP = "proj_67916afd", "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _holiday(client: TestClient, query: str = "") -> dict[str, object]:
    presets = client.get(f"/api/scenarios{query}").json()
    return next(p["effects"] for p in presets if p["scenario"]["id"] == "holiday_season")


def test_a_supermarkets_preview_uses_grocery_effect_sizes(client):
    setup = read_setup(PID, SETUP)
    setup["store"]["type"] = "supermarket"
    write_json(setup_path(PID, SETUP), setup)
    plain = _holiday(client)
    supermarket = _holiday(client, f"?project_id={PID}&setup_id={SETUP}")
    assert plain["traffic"] < 1 < supermarket["traffic"]   # fewer regulars at a convenience store, more grocery trips

    from store_emulator.application.scenarios import get_preset
    custom = get_preset("holiday_season").model_dump(mode="json") | {"id": "custom"}
    preview = client.post(f"/api/scenarios/preview?project_id={PID}&setup_id={SETUP}", json=custom).json()
    assert preview["traffic"] == supermarket["traffic"]
    assert client.post("/api/scenarios/preview", json=custom).json()["traffic"] == plain["traffic"]
    # An unknown layout falls back to the default effect sizes instead of failing the editor.
    assert _holiday(client, f"?project_id={PID}&setup_id=setup_gone")["traffic"] == plain["traffic"]
