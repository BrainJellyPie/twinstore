"""Synergy must resolve layouts inside the selected project, including saved defaults."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import town, town_synergy
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.town import Town
from store_emulator.server.main import app


@pytest.mark.parametrize("setup_id", ["../../outside", "/tmp/outside", "..\\outside"])
def test_synergy_rejects_external_setup_paths_before_starting(monkeypatch, setup_id):
    start = Mock(side_effect=AppError("unsafe input reached the service", 418))
    monkeypatch.setattr(town_synergy, "start_vlm_synergy", start)
    response = TestClient(app).post("/api/projects/proj_test/town/venues/cafe/synergy-vlm", json={"setup_id": setup_id})
    assert response.status_code == 422
    start.assert_not_called()


def test_venue_cannot_persist_external_setup_reference(monkeypatch):
    save = Mock(side_effect=AppError("unsafe input reached the service", 418))
    monkeypatch.setattr(town, "save_town", save)
    response = TestClient(app).put("/api/projects/proj_test/town", json={
        "id": "town_test", "name": "Test", "archetype": "residential", "size_m": 200,
        "focal_venue_id": "focal", "venues": [{"id": "focal", "name": "Test", "category": "convenience",
        "x": 100, "y": 100, "setup_id": "../../outside"}],
    })
    assert response.status_code == 422
    save.assert_not_called()


def test_synergy_rejects_an_invalid_saved_active_layout_before_reading(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    write_json(metadata_path("proj_test"), {"name": "Saved layout validation check"})
    neighborhood = Town.model_validate({
        "id": "town_test", "name": "Test", "archetype": "residential", "size_m": 200,
        "focal_venue_id": "focal", "venues": [{"id": "cafe", "name": "Cafe", "category": "cafe", "x": 100, "y": 100}],
    })
    monkeypatch.setattr(town_synergy, "require_town", lambda _pid: neighborhood)
    monkeypatch.setattr(town_synergy, "read_state", lambda _pid: {"activeSetupId": "../../outside"})
    read = Mock(side_effect=AppError("unsafe input reached file lookup", 418))
    monkeypatch.setattr(town_synergy, "read_setup", read)

    response = TestClient(app).post("/api/projects/proj_test/town/venues/cafe/synergy-vlm", json={})

    assert response.status_code == 400
    read.assert_not_called()
