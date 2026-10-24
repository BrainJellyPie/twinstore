"""Fixes from the second backend audit: store size, analyst units, Shelf Lab, capture placement, fidelity."""

import pytest

from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen import generate_store


def test_a_store_cannot_be_impossibly_large():
    from pydantic import ValidationError

    base = generate_store("mini_mart", seed=0).model_dump(mode="json")
    with pytest.raises(ValidationError, match="at most 256 tiles"):
        Store.model_validate({**base, "grid_size": [100_000, 100_000]})
    assert Store.model_validate({**base, "grid_size": [256, 256]}).grid_size == (256, 256)


def test_the_analyst_sheet_counts_the_walk_in_tiles():
    from store_emulator.engine.run_analyst import comparison_text

    line = comparison_text([("path_tiles", 20, 24, 4, 3, 5)])
    assert "A 20.0 tiles, B 24.0 tiles, B minus A +4.0 tiles" in line and " m," not in line


def test_a_rival_shelf_is_compared_with_our_products_of_its_categories_on_any_layout():
    """Our products had a category only on template racks (rack_desc is a catalog key); on the sample, model-made or
    hand-built layouts no product was in the rival's categories, so overlap read 100%."""
    from store_emulator.domain.capture import CaptureItem, CaptureResult
    from store_emulator.domain.rack import Rack, Slot, SlotItem
    from store_emulator.engine.shelf_lab.rival import compare_rival

    def item(sku: str, name: str) -> SlotItem:
        return SlotItem(sku=sku, name=name, price=150)

    store = Store(id="s", name="Store", type="convenience", grid_size=(8, 8), racks=[
        Rack(id="drinks", rack_name="Drinks", type="fridge", shape=[[1]], position=(3, 3), slots=[
            Slot(block=0, face="N", level=1, items=[item("c", "Coca-Cola 500ml"), item("s", "Sprite 500ml")])]),
        Rack(id="snacks", rack_name="Snacks", type="shelf", shape=[[1]], position=(5, 3), slots=[
            Slot(block=0, face="N", level=1, items=[item("p", "Pringles Original")])]),
    ])
    rival = CaptureResult(image_size=(20, 20), items=[
        CaptureItem(id="1", band=0, level=1, order=0, name="Coca-Cola 500ml", category="soft_drinks", price=140, labeled=True),
        CaptureItem(id="2", band=0, level=1, order=1, name="Fanta Orange 500ml", category="soft_drinks", price=140, labeled=True),
    ])
    comparison = compare_rival(store, rival)
    assert comparison.our_products_in_categories == 2           # the cola and the Sprite; the chips are elsewhere
    assert comparison.matched == 1 and comparison.overlap < 1.0
    assert "Sprite 500ml" in comparison.only_ours and "Pringles Original" not in comparison.only_ours


def test_a_capture_with_a_running_lab_job_is_not_deleted(tmp_path, monkeypatch):
    from store_emulator.application import capture
    from store_emulator.application.errors import AppError
    from store_emulator.application.storage.io import write_json
    from store_emulator.domain.capture import CaptureStatus

    monkeypatch.chdir(tmp_path)
    folder = tmp_path / ".data" / "proj_x" / "captures" / "cap_1"
    write_json(folder.parent.parent / "metadata.json", {"name": "Capture deletion check"})
    write_json(folder / "status.json", CaptureStatus(capture_id="cap_1", status="completed").model_dump(mode="json"))
    write_json(folder / "lab" / "jobs" / "aud_1" / "status.json", {"status": "running"})
    with pytest.raises(AppError) as refused:
        capture.delete_capture("proj_x", "cap_1")
    assert refused.value.status_code == 409 and folder.exists()
    write_json(folder / "lab" / "jobs" / "aud_1" / "status.json", {"status": "completed"})
    capture.delete_capture("proj_x", "cap_1")
    assert not folder.exists()


@pytest.mark.parametrize("face", ["S", "N", "W", "E"])
def test_a_wide_photo_reads_left_to_right_from_the_aisle_on_every_side(face, monkeypatch):
    """Split into new racks, a photo's left part went to the lowest x / y tile whatever the side, so from the north
    and east the shelf read IJKL EFGH ABCD."""
    from store_emulator.domain.capture import Box, CaptureItem, CaptureResult
    from store_emulator.domain.types import Face
    from store_emulator.engine.capture import planogram

    store = generate_store("mini_mart", seed=0)
    items = [CaptureItem(id=f"i{i + 1:02d}", band=0, level=3, order=i, boxes=[Box(x1=i * 100, y1=0, x2=i * 100 + 90, y2=100)],
                         sku=f"cap_{ch}", name=f"Product {ch}", price=100, labeled=True, category="chips")
             for i, ch in enumerate("ABCDEFGHIJKL")]
    photo = CaptureResult(image_size=(1200, 400), items=items, currency="USD", dominant_category="chips")
    runs = planogram._candidate_runs  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(planogram, "_candidate_runs", lambda s, k: [r for r in runs(s, k) if r[1] == Face(face)])
    report = planogram.PlacementReport()
    placed = planogram._place_photo(store, photo, 3, report)  # pyright: ignore[reportPrivateUsage]
    assert placed is not None
    racks = [r for r in placed.racks if r.id in report.rack_ids]
    # Sort the racks as a shopper facing them sees them: left to right.
    dx, dy = {"S": (1, 0), "N": (-1, 0), "W": (0, 1), "E": (0, -1)}[face]   # direction of "right" for the viewer
    ordered = sorted(racks, key=lambda r: r.position[0] * dx + r.position[1] * dy)
    read = " ".join("".join(i.name[-1] for s in r.slots for i in s.items) for r in ordered)
    assert read == "ABCD EFGH IJKL"


def test_a_weekend_scenario_is_not_counted_twice_on_the_neighborhoods_weekend_profile():
    from store_emulator.application.scenarios import get_preset
    from store_emulator.engine.town import scenario_traffic
    from store_emulator.domain.scenario import DayType

    store = generate_store("mini_mart", seed=0)
    weekend = get_preset("heatwave_weekend")
    assert weekend is not None and weekend.day_type == DayType.WEEKEND
    as_weekday = weekend.model_copy(update={"day_type": DayType.WEEKDAY})
    # On the weekend profile only the heat is applied; on a weekday profile the weekend's effect is applied too.
    assert scenario_traffic(weekend, store, None, profile="weekend") == scenario_traffic(as_weekday, store, None)
    assert scenario_traffic(weekend, store, None, profile="weekday") == scenario_traffic(weekend, store, None)


def test_a_study_panel_takes_written_customers_before_their_twins():
    from store_emulator.domain.persona import Persona
    from store_emulator.domain.types import Weekday
    from store_emulator.engine.optimize.evaluate import select_personas

    def person(i: int, twin_of: str = "") -> Persona:
        return Persona(id=f"P{i}", day=Weekday(1), arrival_hour=9, identity="s", age_group="20s", gender="Female",  # type: ignore[arg-type]
                       description=f"d{i % 100}", intent="i", purpose="p", twin_of=twin_of)

    written = [person(i) for i in range(100)]
    pool = written + [person(100 + i, twin_of=f"P{i % 100}") for i in range(2340)]
    panel = select_personas(pool, 100, seed=1)
    assert len(panel) == 100 and not any(p.twin_of for p in panel)
    bigger = select_personas(pool, 150, seed=1)
    assert sum(not p.twin_of for p in bigger) == 100 and len(bigger) == 150
    # Without twins the draw is the one it always was.
    assert select_personas(written, 30, seed=2) == select_personas(list(written), 30, seed=2)


def test_a_saved_layouts_category_price_change_is_its_new_everyday_price():
    """In an A/B test shoppers compare a category price change with the old price; saved as a layout ("edit in
    words"), the new price is the everyday price and nothing is compared with it."""
    from store_emulator.domain.marketing import VariantChange
    from store_emulator.engine.layout_edit import apply_layout_edit
    from store_emulator.engine.marketing.variants import apply_changes

    store = generate_store("mini_mart", seed=0)
    rack = next(r for r in store.racks if r.slots and r.rack_desc)
    change = VariantChange(kind="category_price", category=rack.rack_desc, percent=20)
    tested, _, _ = apply_changes(store, [change])
    saved, applied, _ = apply_layout_edit(store, [change], "USD")
    tested_items = [i for r in tested.racks if r.id == rack.id for s in r.slots for i in s.items]
    saved_items = [i for r in saved.racks if r.id == rack.id for s in r.slots for i in s.items]
    assert tested_items and all(i.regular_price > 0 for i in tested_items)
    assert all(i.regular_price == 0 for i in saved_items) and "remember" not in " ".join(applied)
    assert [i.price for i in saved_items] == [i.price for i in tested_items]
