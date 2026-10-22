"""Applying a rival shelf's price comparison to its pull replaces the earlier adjustment instead of compounding."""

import json
import shutil
from pathlib import Path

from PIL import Image

from store_emulator.application import town as town_service
from store_emulator.application.shelf_lab import RivalRequest, compare_rival_capture
from store_emulator.application.storage.io import DATA_DIR, read_json, write_json
from store_emulator.domain.capture import Box, CaptureItem, CaptureResult, CaptureStatus
from store_emulator.domain.store import Store
from store_emulator.domain.town import TownSpec

P = "proj_67916afd"
SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / P


def test_applying_again_does_not_compound(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(SAMPLE, Path(DATA_DIR) / P)
    store = Store.model_validate(read_json(Path(DATA_DIR) / P / "setups" / "setup_eaf5.json")["store"])
    products = [i for r in store.racks for s in r.slots for i in s.items][:5]
    items = [CaptureItem(id=f"i{k + 1:02d}", band=0, level=3, order=k, boxes=[Box(x1=k * 100, y1=0, x2=k * 100 + 90, y2=100)],
                         sku=f"cap_{k}", name=p.name, price=round(p.price * 0.8), labeled=True)
             for k, p in enumerate(products)]   # the rival sells the same products 20 % cheaper
    folder = Path(DATA_DIR) / P / "captures" / "cap_rival1"
    folder.mkdir(parents=True)
    Image.new("RGB", (600, 200)).save(folder / "image.jpg")
    result = CaptureResult(image_size=(600, 200), items=items, currency=store.currency or "USD")
    write_json(folder / "result.json", json.loads(result.model_dump_json()))
    write_json(folder / "status.json", CaptureStatus(capture_id="cap_rival1", status="completed").model_dump(mode="json"))
    town = town_service.generate(P, TownSpec(seed=1))
    rival = next(v for v in town.venues if v.category.value == "convenience" and not v.is_focal)

    request = RivalRequest(setup_id="setup_eaf5", venue_id=rival.id, apply=True, match_with_model=False)
    first = compare_rival_capture(P, "cap_rival1", request)
    assert first.comparison.suggested_pull_factor is not None and first.attractiveness != rival.attractiveness
    again = [compare_rival_capture(P, "cap_rival1", request) for _ in range(2)]
    assert [r.attractiveness for r in again] == [first.attractiveness] * 2
    assert all(r.previous_attractiveness == rival.attractiveness for r in [first, *again])
    # A pull set by hand afterwards is the new starting point.
    town = town_service.get_town(P)
    assert town is not None
    edited = town.model_copy(update={"venues": [v.model_copy(update={"attractiveness": 1.0}) if v.id == rival.id else v
                                                for v in town.venues]})
    town_service.save_town(P, edited, expected=town)
    later = compare_rival_capture(P, "cap_rival1", request)
    assert later.previous_attractiveness == 1.0
    assert later.attractiveness == round(1.0 * first.comparison.suggested_pull_factor, 3)
