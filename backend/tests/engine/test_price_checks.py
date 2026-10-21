import csv
import io
from datetime import date

import pytest

from store_emulator.domain.price_checks import PriceCheckScope
from store_emulator.engine.analysis.price_checks import COLUMNS, price_check_csv, review_price_checks

SCOPE = PriceCheckScope(store_ref="store-1", audit_date=date(2026, 10, 21))


def data(*rows: dict[str, object]) -> bytes:
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=COLUMNS); writer.writeheader()
    for row in rows:
        writer.writerow({"check_id": "check-1", "sku": "tea", "pack_reference": "box-20", "checked_on": "2026-10-21", "currency": "USD", "price_minor": 200, "terms": "public", **row})
    return out.getvalue().encode()


def test_exact_pair_and_unmatched_checks_with_separate_currency_sums():
    report = review_price_checks(data({}, {"check_id": "lower", "price_minor": 300}, {"check_id": "missing"}, {"check_id": "krw", "currency": "KRW"}),
        data({"price_minor": 300}, {"check_id": "lower", "price_minor": 200}, {"check_id": "checkout-only"}, {"check_id": "krw", "currency": "KRW", "price_minor": 201}), SCOPE)
    assert len(report.rows) == 5 and report.excluded_count == 2
    usd = next(t for t in report.totals if t.currency == "USD")
    assert (usd.higher, usd.lower, usd.equal, usd.positive_difference_minor, usd.negative_difference_minor, usd.net_difference_minor) == (1, 1, 0, 100, -100, 0)
    exported = list(csv.DictReader(io.StringIO(price_check_csv(report))))
    assert next(r for r in exported if r["check_id"] == "lower")["difference_minor"] == "-100"
    assert next(r for r in exported if r["check_id"] == "missing")["difference_minor"] == ""


@pytest.mark.parametrize("field,value", [
    ("check_id", ""), ("check_id", " x"), ("sku", "x "), ("sku", "x\n"), ("pack_reference", "x\u200b"), ("check_id", "x" * 121),
    ("price_minor", ""), ("price_minor", "-1"), ("price_minor", "+1"), ("price_minor", "1.0"), ("price_minor", "1e2"),
    ("price_minor", "NaN"), ("price_minor", "Infinity"), ("price_minor", "１２"), ("price_minor", "1_000"), ("price_minor", " 1"), ("price_minor", 1_000_000_000_001),
    ("currency", "usd"), ("currency", "USDD"), ("currency", "USD\n"), ("checked_on", "2026-02-29"), ("checked_on", "20261021"), ("checked_on", "0"),
    ("terms", ""), ("terms", "member"),
])
def test_invalid_observations_fail_without_partial_results(field, value):
    with pytest.raises(ValueError, match="row 3: invalid"):
        review_price_checks(data({}, {"check_id": "second", field: value}), data({}), SCOPE)


@pytest.mark.parametrize("change,flag", [({"sku": "Tea"}, "sku_mismatch"), ({"pack_reference": "box-10"}, "pack_mismatch"),
    ({"currency": "KRW"}, "currency_mismatch"), ({"checked_on": "2026-10-20"}, "outside_audit_date"),
    ({"checked_on": "2026-10-22"}, "outside_audit_date"), ({"terms": "conditional"}, "terms_unverified"), ({"terms": "unknown"}, "terms_unverified")])
def test_exclusions_on_either_source_never_produce_a_difference(change, flag):
    for left, right in [(data(change), data({})), (data({}), data(change))]:
        result = review_price_checks(left, right, SCOPE)
        assert result.rows[0].flags == [flag]
        assert result.rows[0].difference_minor is None and result.rows[0].relation == "unavailable"
        assert result.totals == [] and result.excluded_count == 1


def test_all_matching_failures_are_retained_together():
    result = review_price_checks(data({}), data({"sku": "other", "pack_reference": "loose", "currency": "EUR", "checked_on": "2026-10-20", "terms": "conditional"}), SCOPE)
    assert result.rows[0].flags == ["sku_mismatch", "pack_mismatch", "currency_mismatch", "outside_audit_date", "terms_unverified"]


def test_header_only_side_and_case_sensitive_full_outer_union():
    left = data({"check_id": "A"}, {"check_id": "a"})
    for labels, checkouts, flag in [(left, data(), "missing_checkout"), (data(), left, "missing_label")]:
        report = review_price_checks(labels, checkouts, SCOPE)
        assert [r.check_id for r in report.rows] == ["A", "a"]
        assert all(r.flags == [flag] and r.difference_minor is None for r in report.rows)
    with pytest.raises(ValueError, match="at least one"):
        review_price_checks(data(), data(), SCOPE)


def test_duplicate_checks_rejected_but_repeated_sku_remains_explicit():
    for labels, checkouts in [(data({}, {}), data({})), (data({}), data({}, {}))]:
        with pytest.raises(ValueError, match="duplicate check_id"):
            review_price_checks(labels, checkouts, SCOPE)
    report = review_price_checks(data({}, {"check_id": "repeat"}), data({}, {"check_id": "repeat"}), SCOPE)
    assert report.totals[0].comparable == 2 and report.totals[0].equal == 2


@pytest.mark.parametrize("bad", [b"", b"\xff", b"wrong,headers\n", data({}) + b"\n", data({}) + b'"unterminated', data({}) + b"extra,row,with,too,many,fields,x,y\n", data({}).replace(b"sku,", b"check_id,"), data({"sku": "x" * 150_000})])
def test_malformed_csv_is_rejected(bad):
    with pytest.raises(ValueError): review_price_checks(bad, data({}), SCOPE)


def test_limits_zero_prices_max_values_exact_sums_and_rounding():
    labels = data(*({"check_id": str(i), "price_minor": 0} for i in range(2000)))
    checkouts = data(*({"check_id": str(i), "price_minor": 1_000_000_000_000} for i in range(2000)))
    report = review_price_checks(labels, checkouts, SCOPE)
    assert report.totals[0].positive_difference_minor == 2_000_000_000_000_000  # Below JS safe-integer bound.
    assert report.totals[0].higher == 2000
    assert review_price_checks(data({"price_minor": 0}), data({"price_minor": 0}), SCOPE).rows[0].relation == "equal"
    with pytest.raises(ValueError, match="2,000 rows"):
        review_price_checks(labels + b"extra,tea,box,2026-10-21,USD,0,public\n", checkouts, SCOPE)
    # Valid whitespace-free quoted fields have bounded length even below the byte limit.
    for source in (0, 1):
        parts = [labels, checkouts]; parts[source] = b"x" * (2 * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match="2 MB"): review_price_checks(*parts, SCOPE)


def test_unicode_bom_reordered_headers_csv_safety_and_numeric_export():
    fields = list(reversed(COLUMNS)); out = io.StringIO(); writer = csv.writer(out); writer.writerow(fields)
    values = {"check_id": "=SUM(1,2)", "sku": "차,茶", "pack_reference": "@box", "checked_on": "2026-10-21", "currency": "USD", "price_minor": 201, "terms": "public"}
    writer.writerow([values[c] for c in fields])
    report = review_price_checks(b"\xef\xbb\xbf" + out.getvalue().encode(), data({**values, "price_minor": 200}), PriceCheckScope(store_ref="-store", audit_date=SCOPE.audit_date))
    assert report.rows[0].difference_minor == -1
    row = list(csv.DictReader(io.StringIO(price_check_csv(report))))[0]
    assert row["check_id"] == "'=SUM(1,2)" and row["label_pack_reference"] == "'@box" and row["store_ref"] == "'-store"
    assert row["label_sku"] == "차,茶" and row["difference_minor"] == "-1"


def test_digest_binds_side_order_bytes_and_scope_and_order_does_not_change_math():
    left, right = data({}), data({"price_minor": 201})
    original = review_price_checks(left, right, SCOPE)
    assert original.source_sha256 == review_price_checks(left, right, SCOPE).source_sha256
    for a, b, scope in [(right, left, SCOPE), (left.replace(b"\r\n", b"\n"), right, SCOPE), (left, right, SCOPE.model_copy(update={"store_ref": "other"})), (left, right, SCOPE.model_copy(update={"audit_date": date(2026, 10, 20)}))]:
        assert original.source_sha256 != review_price_checks(a, b, scope).source_sha256
    bom = review_price_checks(b"\xef\xbb\xbf" + left, right, SCOPE)
    assert bom.source_sha256 != original.source_sha256 and bom.rows == original.rows


def test_maximum_disjoint_sources_keep_all_four_thousand_missing_checks():
    labels = data(*({"check_id": f"l{i}", "sku": "차" * 120} for i in range(2000)))
    checkouts = data(*({"check_id": f"c{i}"} for i in range(2000)))
    report = review_price_checks(labels, checkouts, SCOPE)
    assert len(report.rows) == report.excluded_count == 4000 and report.totals == []
    assert len(list(csv.DictReader(io.StringIO(price_check_csv(report))))) == 4000


@pytest.mark.parametrize("day", ["0001-01-01", "9999-12-31", "2024-02-29"])
def test_supported_date_extremes_and_leap_day(day):
    scope = PriceCheckScope(store_ref="a", audit_date=date.fromisoformat(day))
    assert review_price_checks(data({"checked_on": day}), data({"checked_on": day}), scope).rows[0].difference_minor == 0
