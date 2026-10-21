import csv
import io

import pytest

from store_emulator.domain.unit_prices import PriceScope
from store_emulator.engine.analysis.unit_prices import COLUMNS, review_unit_prices, unit_price_csv


def scope(**changes):
    return PriceScope.model_validate({"focal_retailer": "ours", "as_of": "2026-10-21", "max_age_days": 7, **changes})


def offer(**changes):
    return {"offer_id": "tea", "comparison_group": "black-tea", "retailer": "ours", "observed_on": "2026-10-21", "currency": "USD",
        "pack_count": "2", "quantity_per_pack": "250", "unit": "g", "price_minor": "300", "availability": "in_stock", "terms": "public", **changes}


def sheet(rows):
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=COLUMNS); writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def test_bundle_normalization_and_minimum_price_gap():
    report = review_unit_prices(sheet([offer(), offer(retailer="other", quantity_per_pack="0.5", unit="kg", pack_count="1", price_minor="250")]), scope())
    own, other = report.rows; c = report.comparisons[0]
    assert own.quantity_in_basis == other.quantity_in_basis == "0.5"
    assert own.unit_price_exact == "600" and other.unit_price_exact == "500"
    assert c.focal_min_minor == "600" and c.competitor_min_minor == "500"
    assert c.gap_minor == "100" and c.gap_percent == "20" and c.relation == "above"
    assert c.focal_offer_ids == ["tea"] and c.competitor_offers == [("other", "tea")]
    rows = list(csv.DictReader(io.StringIO(unit_price_csv(report))))
    assert len(rows) == 3 and rows[-1]["row_type"] == "comparison"
    assert rows[0]["source_sha256"] == report.source_sha256


def test_missing_side_and_eligibility_are_not_filled_with_zero():
    report = review_unit_prices(sheet([offer(), offer(retailer="other", price_minor="0", terms="conditional", availability="out_of_stock", observed_on="2026-10-01")]), scope())
    assert report.rows[1].flags == ["stale", "out_of_stock", "conditional_offer"]
    c = report.comparisons[0]
    assert c.competitor_count == 0 and c.competitor_min_minor is c.gap_minor is c.gap_percent is None
    assert c.relation == "unavailable"


@pytest.mark.parametrize(("key", "value"), [
    ("price_minor", ""), ("price_minor", "-1"), ("price_minor", "NaN"), ("price_minor", "1e3"), ("price_minor", "1.0"), ("price_minor", "1000000000001"),
    ("pack_count", "0"), ("pack_count", "1001"), ("pack_count", "1.5"), ("pack_count", " 1"),
    ("quantity_per_pack", "0"), ("quantity_per_pack", "-0.1"), ("quantity_per_pack", "NaN"), ("quantity_per_pack", "Infinity"),
    ("quantity_per_pack", "0.0001"), ("quantity_per_pack", "1e3"), ("quantity_per_pack", "1000000.001"), ("quantity_per_pack", ".5"),
    ("observed_on", "2026-02-29"), ("observed_on", "20261021"), ("observed_on", "2026-10-21T00:00:00"),
    ("currency", "usd"), ("currency", "USDD"), ("unit", "oz"), ("unit", "L"), ("availability", ""), ("terms", "member"),
    ("offer_id", ""), ("offer_id", "x" * 121), ("retailer", " ours"), ("comparison_group", "tea\n=1"), ("offer_id", "te\u200ba"),
])
def test_invalid_fields_reject_without_silent_coercion(key, value):
    with pytest.raises(ValueError): review_unit_prices(sheet([offer(**{key: value})]), scope())


@pytest.mark.parametrize("data", [b"", b"bad", b"\xff", b'"unfinished', b",".join(c.encode() for c in COLUMNS) + b"\n", b"x" * (2 * 1024 * 1024 + 1)])
def test_empty_malformed_encoding_and_size(data):
    with pytest.raises(ValueError): review_unit_prices(data, scope())


def test_headers_columns_and_duplicate_observation_identity():
    data = sheet([offer()])
    for bad in [data.replace(b"offer_id,", b"retailer,", 1), data.replace(b",terms", b",extra,terms", 1), data + b"\n", data.replace(b",public", b",public,extra")]:
        with pytest.raises(ValueError): review_unit_prices(bad, scope())
    with pytest.raises(ValueError, match="duplicate"):
        review_unit_prices(sheet([offer(), offer(observed_on="2026-10-20")]), scope())
    with pytest.raises(ValueError, match="exactly match"):
        review_unit_prices(data, scope(focal_retailer="OURS"))
    r = review_unit_prices(b"\xef\xbb\xbf" + sheet([offer(offer_id='茶,"A"'), offer(retailer="다른점", offer_id='茶,"A"')]), scope())
    assert len(r.rows) == 2 and r.comparisons[0].relation == "equal"


def test_inclusive_age_limit_future_unknown_and_multiple_flags():
    r = review_unit_prices(sheet([offer(), offer(retailer="limit", observed_on="2026-10-14"),
        offer(retailer="old", observed_on="2026-10-13"), offer(retailer="future", observed_on="2026-10-22", availability="unknown", terms="conditional")]), scope())
    assert r.comparisons[0].competitor_count == 1
    assert r.rows[1].flags == [] and r.rows[2].flags == ["stale"]
    assert r.rows[3].flags == ["future", "unknown_availability", "conditional_offer"]
    same_day = review_unit_prices(sheet([offer(), offer(retailer="other", observed_on="2026-10-20")]), scope(max_age_days=0))
    assert same_day.comparisons[0].competitor_count == 0
    leap = review_unit_prices(sheet([offer(observed_on="2024-02-29")]), scope(as_of="2024-03-01", max_age_days=1))
    assert not leap.rows[0].flags


def test_currency_dimension_and_product_groups_never_pool():
    r = review_unit_prices(sheet([offer(), offer(retailer="other", currency="KRW"), offer(retailer="other", offer_id="volume", unit="ml"),
        offer(retailer="other", offer_id="count", unit="item"), offer(retailer="other", offer_id="green", comparison_group="green-tea")]), scope())
    assert len(r.comparisons) == 5 and all(c.relation == "unavailable" for c in r.comparisons)
    assert len(r.rows) == 5


def test_eligible_minima_all_ties_and_free_prices():
    r = review_unit_prices(sheet([offer(), offer(offer_id="cheaper", price_minor="200"), offer(offer_id="tie", pack_count="1", price_minor="100"),
        offer(retailer="other", price_minor="0"), offer(retailer="another", price_minor="0"), offer(retailer="unknown", availability="unknown", price_minor="0")]), scope())
    c = r.comparisons[0]
    assert c.focal_offer_ids == ["cheaper", "tie"] and c.competitor_offers == [("another", "tea"), ("other", "tea")]
    assert c.focal_count == 3 and c.competitor_count == c.competitor_retailers == 2
    assert c.gap_percent is None and c.relation == "above" and c.competitor_min_minor == "0"
    free = review_unit_prices(sheet([offer(price_minor="0"), offer(retailer="other", price_minor="0")]), scope()).comparisons[0]
    assert free.gap_minor == "0" and free.gap_percent is None and free.relation == "equal"


def test_small_large_and_nearly_equal_prices_preserve_exact_order():
    from fractions import Fraction
    for quantity, unit, price, count in [("0.001", "g", "1000000000000", "1"), ("1000000", "kg", "1", "1000"), ("3", "ml", "1", "1")]:
        r = review_unit_prices(sheet([offer(quantity_per_pack=quantity, unit=unit, price_minor=price, pack_count=count)]), scope()).rows[0]
        assert Fraction(r.unit_price_exact) > 0 and float(r.unit_price_minor) > 0
    r = review_unit_prices(sheet([offer(quantity_per_pack="999999.999", price_minor="999999999999"),
        offer(retailer="other", quantity_per_pack="1000000", price_minor="1000000000000")]), scope())
    assert r.comparisons[0].relation == "above" and r.comparisons[0].gap_exact != "0"
    for small, base in [("g", "kg"), ("ml", "l")]:
        a = offer(unit=small, quantity_per_pack="300", pack_count="3", price_minor="123")
        b = offer(retailer="other", unit=base, quantity_per_pack="0.9", pack_count="1", price_minor="123")
        before = review_unit_prices(sheet([a, b]), scope()).comparisons
        after = review_unit_prices(sheet([b, a]), scope()).comparisons
        assert before == after and before[0].relation == "equal"


def test_row_limit_and_reordered_headers():
    rows = [offer(offer_id=f"tea-{i}") for i in range(2000)]
    assert len(review_unit_prices(sheet(rows), scope()).rows) == 2000
    with pytest.raises(ValueError, match="2,000"): review_unit_prices(sheet([*rows, offer()]), scope())
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=list(reversed(COLUMNS))); writer.writeheader(); writer.writerow(offer())
    assert review_unit_prices(output.getvalue().encode(), scope()).rows[0].inputs.offer_id == "tea"


@pytest.mark.parametrize("quantity", ["0.001", "0.5", "1.5"])
def test_indivisible_item_count_cannot_be_fractional(quantity):
    with pytest.raises(ValueError): review_unit_prices(sheet([offer(unit="item", quantity_per_pack=quantity)]), scope())


def test_export_keeps_signed_numeric_gaps_numeric_and_untrusted_labels_literal():
    r = review_unit_prices(sheet([offer(offer_id="=1+1", comparison_group="@tea", price_minor="200"),
        offer(retailer="-competitor", comparison_group="@tea", price_minor="300")]), scope())
    rows = list(csv.DictReader(io.StringIO(unit_price_csv(r))))
    assert rows[0]["offer_id"] == "'=1+1" and rows[0]["comparison_group"] == "'@tea"
    assert rows[1]["retailer"] == "'-competitor"
    assert rows[-1]["gap_minor"] == "-200"
    assert rows[-1]["gap_exact"] == "-200"
    assert float(rows[-1]["gap_percent"]) == pytest.approx(-100 / 3)
