"""Duplicating detected copies of one offer must not change a saved venue adjustment."""

import pytest

from store_emulator.application import town as towns
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import read_setup, setup_path
from store_emulator.domain.capture import CaptureItem
from store_emulator.domain.rack import SlotItem
from tests.engine.test_rival_comparison_boundaries import pair
from tests.server.test_shelf_lab_start_snapshot import CID, lab
from tests.server.test_simulation_setup_races import PID, SID, layout
from tests.server.test_town_save_lifecycle import neighborhood


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("uppercase", [False, True])
def test_more_identical_detections_leave_price_and_pull_unchanged(neighborhood, lab, reverse, uppercase):
    client, town = neighborhood
    _, _, _, folder = lab
    store, capture = pair(our_price=100, rival_price=200)
    capture.currency = "USD"
    store.racks[0].slots[0].items.append(SlotItem(sku="coffee", name="Coffee", price=200))
    data = read_setup(PID, SID)
    write_json(setup_path(PID, SID), {**data, "store": store.model_dump(mode="json")})
    tea = capture.items[0]
    for copies in (1, 9, 2):
        capture.items = [tea.model_copy(update={"id": f"tea-{i}", "level": i % 4 + 1,
            "name": "TEA" if uppercase and i % 2 else "Tea"}) for i in range(copies)] + [
            CaptureItem(id="coffee", band=0, level=1, order=copies, name="Coffee", price=100, labeled=True)]
        if reverse:
            capture.items.reverse()
        write_json(folder / "result.json", capture.model_dump(mode="json"))
        source = (folder / "result.json").read_bytes()
        response = client.post(f"/api/projects/{PID}/captures/{CID}/rival", json={
            "setup_id": SID, "venue_id": "cafe", "apply": True, "match_with_model": False,
        })
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["comparison"]["price_index"] == pytest.approx(1)
        assert report["comparison"]["rival_products"] == 2 and len(report["comparison"]["prices"]) == 2
        assert report["attractiveness"] == town.get_venue("cafe").attractiveness
        assert towns.get_town(PID).get_venue("cafe").attractiveness == report["attractiveness"]
        assert (folder / "result.json").read_bytes() == source
