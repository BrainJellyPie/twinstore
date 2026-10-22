import csv
import io

import pytest
from pydantic import ValidationError

from store_emulator.domain.field_pilot import FieldPilot, PilotRequest
from store_emulator.domain.staff_pitch import PitchProduct, PitchVariant
from store_emulator.engine.marketing.field_pilot import allocate_pilot, analyze_pilot, observations_csv, parse_observations


def design(**changes):
    return PilotRequest.model_validate({"name": "Tea wording", "eligibility": "First tea aisle encounter per customer", "outcome_window": "This visit",
                                       "blocks": [{"staff_id": "s1", "shift_id": "am", "encounters": 20}, {"staff_id": "s1", "shift_id": "pm", "encounters": 20}], **changes})


def pilot(**changes):
    req = design(**changes)
    return FieldPilot(pilot_id="pilot_test", pitch_id="pit_test", created_at="now", updated_at="now", design=req,
                      product=PitchProduct(sku="tea", name="Tea", price=2000, currency="KRW"),
                      variants=(PitchVariant(name="Current", script="Hello"), PitchVariant(name="New", script="Can I help?")),
                      context="Tea shelf", product_facts="", assignments=allocate_pilot("pilot_test", req))


def csv_bytes(p, change=None):
    rows = list(csv.DictReader(io.StringIO(observations_csv(p))))
    if change:
        change(rows)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return out.getvalue().encode()


def test_assignment_is_balanced_reproducible_and_stratified():
    p = pilot()
    assert p.assignments == allocate_pilot("pilot_test", design())
    assert [a.arm for a in p.assignments] != [a.arm for a in pilot(seed=2).assignments]
    for shift in ("am", "pm"):
        rows = [a for a in p.assignments if a.shift_id == shift]
        assert sum(a.arm == "A" for a in rows) == sum(a.arm == "B" for a in rows) == 10
        assert [a.sequence for a in rows] == list(range(1, 21))
    assert len({a.assignment_id for a in p.assignments}) == 40
    reverse = pilot(blocks=list(reversed(design().model_dump()["blocks"])))
    assert [a.arm for a in p.assignments if a.shift_id == "am"] == [a.arm for a in reverse.assignments if a.shift_id == "am"]


@pytest.mark.parametrize("changes", [
    {"blocks": [{"staff_id": "s1", "shift_id": "am", "encounters": 41}]},
    {"blocks": [{"staff_id": "s1", "shift_id": "am", "encounters": 20}]},
    {"blocks": [{"staff_id": "s1", "shift_id": "am", "encounters": 20}] * 2},
    {"blocks": [{"staff_id": "=SUM", "shift_id": "am", "encounters": 40}]},
    {"seed": True}, {"seed": -1}, {"eligibility": " "},
])
def test_invalid_precommitments(changes):
    with pytest.raises(ValidationError):
        design(**changes)


def test_unknowns_are_not_nonbuyers_and_delivery_does_not_select_analysis_sample():
    p = pilot()
    a = next(row for row in p.assignments if row.arm == "A")
    a.enrolled = True; a.delivered = False; a.purchased = True
    another = next(row for row in p.assignments if row.arm == "A" and row is not a)
    another.enrolled = True
    analysis = analyze_pilot(p)
    assert (analysis.a.enrolled, analysis.a.observed, analysis.a.purchases, analysis.a.missing_outcomes) == (2, 1, 1, 1)
    assert analysis.a.observed_rate == 1
    assert (analysis.a.missing_bound_low, analysis.a.missing_bound_high) == (0.5, 1)
    assert analysis.a.not_delivered == 1 and analysis.b.observed_rate is None
    assert not analysis.can_finalize and analysis.difference is None and analysis.ci_low is None


def test_final_fixed_sample_effect_keeps_boundary_uncertainty_and_requires_closure():
    p = pilot()
    for row in p.assignments:
        row.enrolled = True; row.delivered = True; row.purchased = row.arm == "B"
    assert analyze_pilot(p).target_completed and analyze_pilot(p).ci_low is None
    p.finalized_at = "closed"
    final = analyze_pilot(p)
    assert final.difference == 1 and 0 < final.ci_low < final.ci_high == 1
    for row in p.assignments:
        row.purchased = False
    null = analyze_pilot(p)
    assert null.difference == 0 and null.ci_low < 0 < null.ci_high


def test_incomplete_targets_and_missing_results_never_get_final_intervals():
    p = pilot()
    for row in p.assignments:
        row.enrolled = False
    assert analyze_pilot(p).can_finalize
    p.finalized_at = "closed"
    result = analyze_pilot(p)
    assert not result.inference_ready and not result.target_completed and result.ci_low is None
    assert "below" in result.interpretation


def test_import_roundtrip_bom_column_reordering_and_no_arm_edits():
    p = pilot()
    assert parse_observations(b"\xef\xbb\xbf" + csv_bytes(p), p) == p.assignments
    rows = list(csv.DictReader(io.StringIO(observations_csv(p))))
    rows[0].update(enrolled="1", delivered="0", purchased="1")
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(reversed(rows[0]))); writer.writeheader(); writer.writerows(rows)
    result = parse_observations(out.getvalue().encode(), p)
    assert result[0].enrolled and result[0].purchased and result[0].delivered is False
    assert p.assignments[0].enrolled is None


@pytest.mark.parametrize("mutate,match", [
    (lambda rows: rows.pop(), "full assignment"),
    (lambda rows: rows.append(rows[0]), "duplicate"),
    (lambda rows: rows[0].update(arm="B" if rows[0]["arm"] == "A" else "A"), "cannot be changed"),
    (lambda rows: rows[0].update(pilot_id="pilot_other"), "cannot be changed"),
    (lambda rows: rows[0].update(staff_id="other"), "cannot be changed"),
    (lambda rows: rows[0].update(purchased="1"), "only enrolled"),
    (lambda rows: rows[0].update(enrolled="0", delivered="0"), "only enrolled"),
    (lambda rows: rows[0].update(enrolled="yes"), "must be 0"),
])
def test_bad_observation_rows_are_rejected_as_a_whole(mutate, match):
    p = pilot()
    with pytest.raises(ValueError, match=match):
        parse_observations(csv_bytes(p, mutate), p)
    assert all(a.enrolled is None for a in p.assignments)


@pytest.mark.parametrize("data,match", [(b"\xff", "UTF-8"), (b"x" * (2 * 1024 * 1024 + 1), "2 MB"), (b"", "columns"),
                                       (b"pilot_id,assignment_id,staff_id,shift_id,sequence,arm,enrolled,delivered,delivered", "columns")])
def test_bad_csv_envelopes(data, match):
    with pytest.raises(ValueError, match=match):
        parse_observations(data, pilot())


def test_ids_a_spreadsheet_reformatted_still_match_their_assignment():
    p = pilot(blocks=[{"staff_id": "007", "shift_id": "2026-10-22", "encounters": 40}])

    def excel(rows):   # Excel drops leading zeros and writes dates the US way
        for row in rows:
            row.update(staff_id="7", shift_id="10/22/2026")

    assert parse_observations(csv_bytes(p, excel), p) == p.assignments
    with pytest.raises(ValueError, match="cannot be changed"):
        parse_observations(csv_bytes(p, lambda rows: rows[0].update(staff_id="8")), p)
    with pytest.raises(ValueError, match="cannot be changed"):
        parse_observations(csv_bytes(p, lambda rows: rows[0].update(shift_id="10/23/2026")), p)
