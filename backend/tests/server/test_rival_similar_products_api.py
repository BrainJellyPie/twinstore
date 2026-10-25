"""A mismatched pack size must not alter a saved rival venue's attractiveness."""

import pytest

from store_emulator.application import shelf_lab
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, read_setup, setup_path
from store_emulator.domain.rack import SlotItem
from tests.engine.test_rival_comparison_boundaries import pair
from tests.server.test_shelf_lab_start_snapshot import CID, lab
from tests.server.test_simulation_setup_races import PID, SID, layout
from tests.server.test_town_save_lifecycle import neighborhood


@pytest.mark.parametrize("matching", ["disabled", "unmatched", "failed"])
def test_unconfirmed_variant_cannot_adjust_saved_pull(neighborhood, lab, monkeypatch, matching):
    client, town = neighborhood
    _, _, _, folder = lab
    ours, theirs = "Coca-Cola Original 500ml", "Coca-Cola Original 1500ml"
    store, capture = pair(our_name=ours, rival_name=theirs, our_price=200, rival_price=400)
    capture.currency = "USD"
    data = read_setup(PID, SID)
    write_json(setup_path(PID, SID), {**data, "store": store.model_dump(mode="json")})
    write_json(folder / "result.json", capture.model_dump(mode="json"))
    calls = []

    class Model:
        async def generate_structured_async(self, schema, prompt, user, **kwargs):
            calls.append(user)
            assert theirs in user and ours in user
            if matching == "failed":
                raise RuntimeError("offline provider unavailable")
            return schema.model_validate({"pairs": [{"rival": theirs, "ours": ""}]})

    monkeypatch.setattr(shelf_lab, "assistive_client", lambda *args: Model())
    town_path = metadata_path(PID).parent / "town.json"
    before = town_path.read_bytes()
    response = client.post(f"/api/projects/{PID}/captures/{CID}/rival", json={
        "setup_id": SID, "venue_id": "cafe", "apply": True, "match_with_model": matching != "disabled",
    })
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["comparison"]["matched"] == 0 and report["comparison"]["price_index"] is None
    assert report["comparison"]["suggested_pull_factor"] is None
    assert report["attractiveness"] == town.get_venue("cafe").attractiveness
    assert town_path.read_bytes() == before and not shelf_lab._rival_pulls_path(PID).exists()
    assert len(calls) == int(matching != "disabled")
    assert bool(report["match_note"]) == (matching == "failed")


@pytest.mark.parametrize("other_sku,other_price", [("different", 100), ("different", 400), ("tea", 400)])
@pytest.mark.parametrize("reverse", [False, True])
def test_ambiguous_reference_cannot_adjust_saved_pull(neighborhood, lab, other_sku, other_price, reverse):
    client, town = neighborhood
    _, _, _, folder = lab
    store, capture = pair(our_price=100, rival_price=200)
    capture.currency = "USD"
    store.racks[0].slots[0].items.append(SlotItem(sku=other_sku, name="Tea", price=other_price))
    if reverse:
        store.racks[0].slots[0].items.reverse()
    data = read_setup(PID, SID)
    write_json(setup_path(PID, SID), {**data, "store": store.model_dump(mode="json")})
    write_json(folder / "result.json", capture.model_dump(mode="json"))
    town_path = metadata_path(PID).parent / "town.json"
    before = town_path.read_bytes()
    response = client.post(f"/api/projects/{PID}/captures/{CID}/rival", json={
        "setup_id": SID, "venue_id": "cafe", "apply": True, "match_with_model": False,
    })
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["comparison"]["matched"] == int(other_sku == "tea")
    assert report["comparison"]["price_index"] is None and not report["comparison"]["prices"]
    assert report["comparison"]["suggested_pull_factor"] is None
    assert report["attractiveness"] == town.get_venue("cafe").attractiveness
    assert town_path.read_bytes() == before and not shelf_lab._rival_pulls_path(PID).exists()
