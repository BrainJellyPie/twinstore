import csv
import io

import pytest

from store_emulator.domain.field_pilot import FieldPilot, PilotRequest
from store_emulator.domain.staff_pitch import PitchProduct, PitchVariant
from store_emulator.engine.marketing.field_pilot import allocate_pilot, parse_observations
from store_emulator.engine.marketing.field_pos import COLUMNS, reconcile_pos


def pilot():
    design = PilotRequest(name="POS test", eligibility="Each customer once", outcome_window="Same visit",
                          blocks=[{"staff_id": "s1", "shift_id": "am", "encounters": 20},
                                  {"staff_id": "s1", "shift_id": "pm", "encounters": 20}])
    return FieldPilot(pilot_id="pilot_test", pitch_id="pit_test", created_at="now", updated_at="now", revision=3,
                      design=design, product=PitchProduct(sku="001tea", name="Tea", price=1, currency="USD"),
                      variants=(PitchVariant(name="A", script="Hello"), PitchVariant(name="B", script="Welcome")),
                      context="Tea aisle", product_facts="", assignments=allocate_pilot("pilot_test", design))


def source(rows):
    out = io.StringIO(); writer = csv.writer(out); writer.writerow(COLUMNS)
    writer.writerows([["pilot_test", *r] for r in rows])
    return out.getvalue().encode()


def test_exact_pos_matching_proposes_only_unknown_enrolled_purchases_and_preserves_everything_else():
    p = pilot(); a = p.assignments
    for i in (0, 1, 2, 5, 6, 7, 20):
        a[i].enrolled = True; a[i].delivered = False
    a[1].purchased = False; a[2].purchased = True; a[3].enrolled = False; a[6].purchased = False
    before = p.model_dump()
    rows = [[a[i].assignment_id, f"tx{i}", "001tea", "1"] for i in range(5)]
    rows += [[a[0].assignment_id, "tx_extra", "001tea", "0.25"],
             [a[0].assignment_id, "tx0", "snack", "3"],
             [a[5].assignment_id, "tx5", "001Tea", "9"],
             [a[6].assignment_id, "tx6", "001tea", "0"],
             ["unknown_slot", "tx_unknown", "001tea", "2"], ["", "tx_unlinked", "001tea", "2"]]
    report = reconcile_pos(p, source(rows))
    matches = {m.assignment_id: m for m in report.matches}
    assert report.proposed_purchases == 1 and report.transactions == 10 and report.source_rows == 11
    assert report.linked_assignments == 7 and report.enrolled_without_evidence == 4
    assert matches[a[0].assignment_id].target_units == 1.25
    assert [matches[a[i].assignment_id].status for i in range(7)] == [
        "proposed_purchase", "conflicting_purchase", "already_recorded", "not_enrolled", "not_enrolled",
        "no_target_evidence", "no_target_evidence",
    ]
    assert matches["unknown_slot"].status == "unknown_assignment" and matches[""].status == "unlinked"
    assert p.model_dump() == before
    proposed = parse_observations(report.candidate_csv.encode(), p)
    expected = p.model_copy(deep=True); expected.assignments[0].purchased = True
    assert proposed == expected.assignments
    assert proposed[0].delivered is False and proposed[20].purchased is None
    assert reconcile_pos(expected, source(rows)).proposed_purchases == 0


def test_source_order_and_multiple_receipts_do_not_inflate_conversion_or_mix_shifts():
    p = pilot()
    for i in (0, 20):
        p.assignments[i].enrolled = True
    rows = [[p.assignments[0].assignment_id, f"tx{i}", "001tea", "0.000001"] for i in range(3)]
    report = reconcile_pos(p, source(rows))
    reversed_report = reconcile_pos(p, source(list(reversed(rows))))
    assert report.matches == reversed_report.matches and report.candidate_csv == reversed_report.candidate_csv
    assert report.source_sha256 != reversed_report.source_sha256
    assert report.proposed_purchases == 1 and report.enrolled_without_evidence == 1
    assert report.matches[0].target_units == 0.000003
    assert report.matches[0].shift_id == "am"
    assert parse_observations(report.candidate_csv.encode(), p)[20].purchased is None


@pytest.mark.parametrize("value", ["-1", "nan", "NaN", "Infinity", "1e3", "1.0000001", "1000001", "", " 1", "9" * 100])
def test_invalid_quantities_are_rejected(value):
    with pytest.raises(ValueError, match="net_quantity"):
        reconcile_pos(pilot(), source([["", "tx", "001tea", value]]))


@pytest.mark.parametrize("rows,message", [
    ([["a", "tx", "tea", "1"], ["a", "tx", "tea", "2"]], "duplicate transaction/SKU"),
    ([["a", "tx", "tea", "1"], ["b", "tx", "snack", "1"]], "multiple assignments"),
    ([["", "tx", "tea", "1"], ["a", "tx", "snack", "1"]], "multiple assignments"),
    ([["a", "=formula", "tea", "1"]], "anonymous"),
    ([["a", "tx", "", "1"]], "SKU"),
    ([["a", "tx", "tea\n", "1"]], "SKU"),
])
def test_ambiguous_or_invalid_links_reject_the_entire_preview(rows, message):
    with pytest.raises(ValueError, match=message):
        reconcile_pos(pilot(), source(rows))


@pytest.mark.parametrize("data,message", [
    (b"\xff", "UTF-8"), (b"", "exactly once"), (b"pilot_id,assignment_id,transaction_id,sku,sku\n", "exactly once"),
    ((",".join(COLUMNS) + "\n").encode(), "at least one"),
    ((",".join(COLUMNS) + "\nwrong,a,tx,tea,1\n").encode(), "pilot ID"),
    ((",".join(COLUMNS) + "\npilot_test,a,tx,tea,1,extra\n").encode(), "columns"),
    ((",".join(COLUMNS) + '\npilot_test,a,tx,"tea,1').encode(), "Malformed"),
])
def test_schema_and_scope_errors_are_explicit(data, message):
    with pytest.raises(ValueError, match=message):
        reconcile_pos(pilot(), data)


def test_bom_reordered_columns_and_resource_limits():
    report = reconcile_pos(pilot(), b"\xef\xbb\xbfnet_quantity,sku,transaction_id,assignment_id,pilot_id\n1,001tea,tx,,pilot_test\n")
    assert report.matches[0].status == "unlinked"
    with pytest.raises(ValueError, match="2 MB"):
        reconcile_pos(pilot(), b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="10,000"):
        reconcile_pos(pilot(), source([["", f"tx{i}", "tea", "1"] for i in range(10001)]))
