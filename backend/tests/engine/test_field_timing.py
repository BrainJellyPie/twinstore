import csv
import hashlib
import io

import pytest

from store_emulator.domain.field_pilot import FieldPilot, PilotRequest
from store_emulator.domain.staff_pitch import PitchProduct, PitchVariant
from store_emulator.engine.marketing.field_pilot import allocate_pilot
from store_emulator.engine.marketing.field_timing import review_timing, timing_csv, timing_template


def pilot(counts=(10, 30)):
    design = PilotRequest(name="Offline timing", eligibility="First eligible encounter", outcome_window="This visit",
        blocks=[{"staff_id": f"s{i}", "shift_id": "am", "encounters": n} for i, n in enumerate(counts)])
    p = FieldPilot(pilot_id="pilot_test", pitch_id="pit_test", created_at="now", updated_at="now", finalized_at="closed", revision=2,
        design=design, product=PitchProduct(sku="tea", name="Tea", price=100, currency="USD"),
        variants=(PitchVariant(name="A", script="Hello"), PitchVariant(name="B", script="Welcome")), context="Aisle", product_facts="",
        assignments=allocate_pilot("pilot_test", design))
    for row in p.assignments:
        row.enrolled = True; row.delivered = False; row.purchased = False
    return p


def sheet(p, values=None):
    rows = list(csv.DictReader(io.StringIO(timing_template(p))))
    for index, row in enumerate(rows):
        row["staff_seconds"] = values[index] if values is not None else ("1.001" if p.assignments[index].arm == "A" else "2.001")
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def test_complete_times_include_refusals_and_preserve_source():
    p = pilot(); before = p.model_dump(); data = sheet(p)
    result = review_timing(p, data)
    assert result.complete and result.timed == result.planned == 40
    assert result.a.mean_seconds == 1.001 and result.b.mean_seconds == 2.001
    assert result.difference_seconds == 1 and result.source_sha256 == hashlib.sha256(data).hexdigest()
    assert [b.timed for b in result.blocks] == [10, 30]
    assert p.model_dump() == before
    for row in p.assignments: row.purchased = True; row.delivered = True
    assert review_timing(p, data) == result


def test_template_and_partial_data_never_impute_or_compare_partial_arms():
    p = pilot(); template = review_timing(p, timing_template(p).encode())
    assert template.timed == 0 and template.a.mean_seconds is None
    values = ["0" if row.arm == "A" else "" for row in p.assignments]
    result = review_timing(p, sheet(p, values))
    assert not result.complete and result.a.timed == 20 and result.b.timed == 0
    assert result.a.mean_seconds is result.b.mean_seconds is result.difference_seconds is None
    assert sum(r.staff_seconds == 0 for r in result.rows) == 20
    assert sum(r.staff_seconds is None for r in result.rows) == 20
    exported = list(csv.DictReader(io.StringIO(timing_csv(result))))
    assert all(r["mean_a_seconds"] == "" and r["complete"] == "0" for r in exported)
    assert exported[0]["revision"] == "2" and exported[0]["source_sha256"] == result.source_sha256


def test_unequal_blocks_use_planned_encounter_weights():
    p = pilot()
    data = sheet(p, ["0" if r.arm == "A" else "100" if r.staff_id == "s0" else "20" for r in p.assignments])
    result = review_timing(p, data)
    assert result.a.mean_seconds == 0
    assert result.b.mean_seconds == result.difference_seconds == 40  # Not the unweighted block average, 60.
    assert result.b.max_seconds == 100


@pytest.mark.parametrize("raw", ["-1", "-0", "+1", "NaN", "Infinity", "1e2", "0.0001", "3600.001", "3601", "1,5", " ", "1 ", "１", "١", "1\x00", "1\n2", "123456789"])
def test_rejects_nonfinite_ambiguous_and_out_of_range_time(raw):
    p = pilot(); values = ["1"] * 40; values[0] = raw
    with pytest.raises(ValueError, match="staff_seconds"):
        review_timing(p, sheet(p, values))


@pytest.mark.parametrize("raw,expected", [("0", 0), ("0.001", 0.001), ("3600.000", 3600), ("0001.001", 1.001)])
def test_inclusive_numeric_boundaries(raw, expected):
    p = pilot(); report = review_timing(p, sheet(p, [raw] * 40))
    assert report.a.mean_seconds == report.b.mean_seconds == expected
    assert report.difference_seconds == 0


@pytest.mark.parametrize("data,pattern", [
    (b"", "exactly once"), (b"pilot_id,assignment_id,staff_seconds\n", "at least one"),
    (b"pilot_id,assignment_id,staff_seconds,extra\n", "exactly once"),
    (b"pilot_id,assignment_id,assignment_id\n", "exactly once"),
    (b"pilot_id,assignment_id,staff_seconds\n\n", "number of columns"),
    (b'pilot_id,assignment_id,staff_seconds\n"unterminated', "Malformed"),
    (b"\xff", "UTF-8"), (b"x" * (2 * 1024 * 1024 + 1), "2 MB"),
])
def test_empty_malformed_encoding_schema_and_size_limits(data, pattern):
    with pytest.raises(ValueError, match=pattern): review_timing(pilot(), data)


def test_duplicate_blank_unknown_and_cross_pilot_rows_are_rejected():
    p = pilot(); rows = timing_template(p).splitlines(); first = rows[1]
    for record, message in [(first, "duplicate"), ("pilot_test,other,1", "does not match"),
                            (first.replace("pilot_test", "pilot_other", 1), "does not match")]:
        data = "\n".join([rows[0], first, record]).encode()
        with pytest.raises(ValueError, match=message): review_timing(p, data)


def test_bom_reordered_columns_quoted_fields_and_missing_rows():
    p = pilot(); aid = p.assignments[0].assignment_id
    data = f'\ufeffstaff_seconds,assignment_id,pilot_id\r\n"0.001","{aid}","pilot_test"\r\n'.encode()
    result = review_timing(p, data)
    assert result.source_rows == result.timed == 1 and not result.complete
    assert result.rows[0].staff_seconds == 0.001
    assert sum(r.staff_seconds is None for r in result.rows) == 39
    assert result.a.mean_seconds is result.b.mean_seconds is result.difference_seconds is None


@pytest.mark.parametrize("mutate", [
    lambda p: setattr(p, "finalized_at", ""), lambda p: p.assignments.pop(),
    lambda p: p.assignments.append(p.assignments[0]),
    lambda p: setattr(p.assignments[0], "enrolled", False), lambda p: setattr(p.assignments[0], "enrolled", None),
    lambda p: setattr(p.assignments[0], "delivered", None), lambda p: setattr(p.assignments[0], "purchased", None),
    lambda p: setattr(p.assignments[0], "staff_id", "other"), lambda p: setattr(p.assignments[0], "shift_id", "other"),
    lambda p: setattr(p.assignments[0], "arm", "B" if p.assignments[0].arm == "A" else "A"),
])
def test_open_incomplete_or_tampered_fixed_plans_are_rejected(mutate):
    p = pilot(); data = sheet(p); mutate(p)
    with pytest.raises(ValueError): review_timing(p, data)
    with pytest.raises(ValueError): timing_template(p)


def test_row_order_does_not_change_estimates_and_exact_small_difference_survives():
    p = pilot(); values = ["1"] * 40
    index = next(i for i, r in enumerate(p.assignments) if r.arm == "A")
    values[index] = "1.001"
    data = sheet(p, values); lines = data.splitlines()
    first = review_timing(p, data); reordered = review_timing(p, b"\n".join([lines[0], *reversed(lines[1:])]))
    assert first.difference_seconds == reordered.difference_seconds == -0.00005
    assert first.a == reordered.a and first.rows == reordered.rows
    assert first.source_sha256 != reordered.source_sha256


def test_maximum_fixed_plan_and_row_limit():
    p = pilot((2000,) * 5); data = sheet(p, ["3600.000"] * 10000)
    result = review_timing(p, data)
    assert result.complete and result.timed == 10000 and result.a.mean_seconds == 3600
    with pytest.raises(ValueError, match="10,000"):
        review_timing(p, data + data.splitlines()[1] + b"\n")


def test_export_preserves_unknown_zero_and_formula_escaping():
    p = pilot(); values = [""] * 40; values[0] = "0"
    result = review_timing(p, sheet(p, values)); result.rows[0].staff_id = "\t=SUM(1,1)"
    rows = list(csv.DictReader(io.StringIO(timing_csv(result))))
    assert rows[0]["staff_seconds"] == "0.0" and rows[1]["staff_seconds"] == ""
    assert rows[0]["staff_id"] == "'\t=SUM(1,1)"
    assert rows[0]["difference_seconds"] == ""
