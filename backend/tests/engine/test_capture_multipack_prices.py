"""A named-container rate must not price a whole observed multipack."""
import pytest
from PIL import Image

from store_emulator.domain.capture import CaptureResult, ShelfItemLabel
from store_emulator.engine.capture.catalog_match import price_minor_units
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.planogram import replace_rack_face
from store_emulator.engine.capture.recognize import FacingGroup, describe
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("size", [
    "6 PACK", "6-pack", "pack of 6", "6 pk", "6 count", "6 ct", "6입", "6개입", "6本入り", "6個入り",
    "6 x 500 ml", "6×500ml", "6 * 0.5 L", "500 ml x 6", "2 x 3 x 500 ml", "1 x 6 x 500 ml",
    "６ ＰＡＣＫ",
    "6 bottles", "6-bottle", "6 cans", "6-can", "6 jars", "6 jar", "6병", "6캔", "6本", "6缶",
    "６ ＢＯＴＴＬＥＳ",
])
@pytest.mark.parametrize("guess", [None, 1.0])
def test_a_bottle_rate_cannot_override_a_multipack_price(size, guess):
    label = ShelfItemLabel(name="Cola", size=size, price_text="$1.00 / BOTTLE", price=guess)
    assert price_minor_units(label, "USD", 699) is None


@pytest.mark.parametrize("tag,currency", [
    ("$1 per bottle", "USD"), ("$1 / can", "USD"), ("$1 per jar", "USD"),
    ("$1∕bottle", "USD"), ("$1⁄bottle", "USD"), ("＄１／ＢＯＴＴＬＥ", "USD"),
    ("병당 1,000원", "KRW"), ("1,000원/캔", "KRW"), ("100円/本", "JPY"),
    ("$0.00 / bottle", "USD"),
])
def test_named_container_rates_are_guarded_when_the_count_is_in_the_product_name(tag, currency):
    label = ShelfItemLabel(name="Cola 6 PACK", size="500 ml", price_text=tag, price=1)
    assert price_minor_units(label, currency, 699) is None


@pytest.mark.parametrize("size", [
    "", "500 ml", "1 PACK", "pack of 1", "1 x 500 ml", "500 ml x 1", "B6 PACK", "6 x 4 cm",
    "1 bottle", "1 can", "1 jar", "1병", "1本", "B6 bottles", "1.5 bottles", "6 bottled flavours",
])
def test_a_single_container_or_non_count_text_keeps_its_bottle_price(size):
    assert price_minor_units(ShelfItemLabel(name="Cola", size=size, price_text="$1 per bottle"), "USD", 699) == 100


@pytest.mark.parametrize("size", ["6 PACK", "6 BOTTLES", "6 CANS"])
@pytest.mark.parametrize("tag", ["$6.00", "$6 per pack", "$6 / PACK", "$6 each", "$6 per item", "$6/ea"])
def test_prices_for_the_selling_pack_remain_exact(tag, size):
    assert price_minor_units(ShelfItemLabel(name=f"Cola {size}", size=size, price_text=tag), "USD", 699) == 600


@pytest.mark.parametrize("size", ["6 PACK", "6 BOTTLES", "6 CANS"])
def test_a_container_rate_preserves_an_existing_multipack_offer(size):
    store = target_store()
    original = store.racks[0].slots[0].items[0]
    original.name, original.price = f"Cola {size}", 699
    before = store.model_dump_json()
    with Image.new("RGB", (100, 80), "white") as photo:
        detection = Detection(x1=0, y1=0, x2=40, y2=60, band=0)
        label = ShelfItemLabel(name=f"Cola {size}", size=size, category="soft drink", price_text="$1 / BOTTLE", price=1)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label)
        items, _ = build_items(make_frame(photo), [group], [3], currency="USD", rack_type="shelf")
        assert items[0].labeled and items[0].price_estimated
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    assert len(placed) == 1 and placed[0].price == 699
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == before and updated.racks[1] == store.racks[1]
