"""Rival pull and its reapplication baseline share one project/town transaction."""

import pytest

from store_emulator.application import projects, shelf_lab, town as towns
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path
from tests.server.test_shelf_lab_start_snapshot import CID, lab, overlap
from tests.server.test_simulation_setup_races import PID, SID, layout
from tests.server.test_town_save_lifecycle import neighborhood


@pytest.fixture
def rival(neighborhood, lab, monkeypatch):
    client, town = neighborhood
    original = shelf_lab.compare_rival

    def compare(*args, **kwargs):
        return original(*args, **kwargs).model_copy(update={"suggested_pull_factor": 1.25})

    monkeypatch.setattr(shelf_lab, "compare_rival", compare)
    return client, town


def apply(client, venue="cafe"):
    return client.post(f"/api/projects/{PID}/captures/{CID}/rival", json={
        "setup_id": SID, "venue_id": venue, "apply": True, "match_with_model": False,
    })


def test_deletion_cannot_interleave_between_town_and_rival_baseline_writes(rival, monkeypatch):
    client, _ = rival
    applied, deleted = overlap(monkeypatch, shelf_lab, "write_json", lambda: apply(client),
                               lambda: client.delete(f"/api/projects/{PID}"))
    assert applied.status_code == deleted.status_code == 200
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("same_venue", [False, True])
def test_overlapping_applications_keep_baselines_without_compounding(rival, monkeypatch, same_venue):
    client, town = rival
    second_id = "cafe" if same_venue else "another"
    if not same_venue:
        town = town.model_copy(update={"venues": [*town.venues,
            town.get_venue("cafe").model_copy(update={"id": second_id})]})
        towns.save_town(PID, town)
    first, second = overlap(monkeypatch, shelf_lab, "write_json",
                             lambda: apply(client), lambda: apply(client, second_id))
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json()["attractiveness"] == second.json()["attractiveness"]
    baseline = town.get_venue("cafe").attractiveness
    pulls = read_json(shelf_lab._rival_pulls_path(PID))
    assert set(pulls) == {"cafe", second_id}
    assert all(record["base"] == baseline for record in pulls.values())
    again = apply(client, second_id)
    assert again.status_code == 200
    assert again.json()["attractiveness"] == first.json()["attractiveness"]


def test_apply_waiting_on_project_deletion_cannot_recreate_it(rival, monkeypatch):
    client, _ = rival
    deleted, applied = overlap(monkeypatch, projects, "remove_tree",
        lambda: client.delete(f"/api/projects/{PID}"), lambda: apply(client))
    assert deleted.status_code == 200 and applied.status_code == 404
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("already_applied", [False, True])
def test_baseline_write_failure_restores_town_before_retry(rival, monkeypatch, already_applied):
    client, _ = rival
    if already_applied:
        assert apply(client).status_code == 200
    path = shelf_lab._rival_pulls_path(PID)
    old_baseline = path.read_bytes() if path.exists() else None
    before = towns.get_town(PID)
    original_compare, original_write = shelf_lab.compare_rival, shelf_lab.write_json
    monkeypatch.setattr(shelf_lab, "compare_rival", lambda *a, **kw:
        original_compare(*a, **kw).model_copy(update={"suggested_pull_factor": 1.5}))

    def fail_write(*args, **kwargs):
        raise OSError("injected baseline write failure")

    monkeypatch.setattr(shelf_lab, "write_json", fail_write)
    with pytest.raises(OSError, match="injected"):
        shelf_lab.compare_rival_capture(PID, CID, shelf_lab.RivalRequest(
            setup_id=SID, venue_id="cafe", apply=True, match_with_model=False))
    assert towns.get_town(PID) == before
    assert (path.read_bytes() if path.exists() else None) == old_baseline
    monkeypatch.setattr(shelf_lab, "write_json", original_write)
    retried = apply(client)
    assert retried.status_code == 200
    assert retried.json()["attractiveness"] == round(retried.json()["previous_attractiveness"] * 1.5, 3)
