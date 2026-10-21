import csv
import io
import random

import pytest

from store_emulator.domain.field_pilot import FieldPilot, PilotRequest
from store_emulator.domain.staff_pitch import PitchProduct, PitchVariant
from store_emulator.engine.marketing.field_pilot import allocate_pilot, analyze_pilot
from store_emulator.engine.marketing.field_sensitivity import analyze_sensitivity, sensitivity_csv


def pilot(single=False):
    design = PilotRequest(name="Offline sensitivity fixture", eligibility="One eligible encounter per shopper",
                          outcome_window="This visit", blocks=[{"staff_id": "s1", "shift_id": "am", "encounters": 40}] if single else [
                              {"staff_id": "s1", "shift_id": "am", "encounters": 20},
                              {"staff_id": "s1", "shift_id": "pm", "encounters": 10},
                              {"staff_id": "s2", "shift_id": "am", "encounters": 10}])
    p = FieldPilot(pilot_id="pilot_test", pitch_id="pit_test", created_at="now", updated_at="now", finalized_at="closed",
                   revision=2, design=design, product=PitchProduct(sku="tea", name="Tea", price=2000, currency="KRW"),
                   variants=(PitchVariant(name="A", script="Hello"), PitchVariant(name="B", script="Can I help?")),
                   context="Tea shelf", product_facts="", assignments=allocate_pilot("pilot_test", design))
    targets = {("s1", "am", "A"): 2, ("s1", "am", "B"): 8, ("s1", "pm", "A"): 4,
               ("s1", "pm", "B"): 1, ("s2", "am", "A"): 3, ("s2", "am", "B"): 2}
    seen = {}
    for row in p.assignments:
        key = (row.staff_id, row.shift_id, row.arm)
        seen[key] = seen.get(key, 0) + 1
        row.enrolled = True; row.delivered = False; row.purchased = seen[key] <= targets[key]
    return p


def test_weighted_deletion_keeps_all_shifts_per_staff_and_all_staff_per_shift():
    p = pilot(); before = p.model_dump()
    report = analyze_sensitivity(p)
    assert report.difference == pytest.approx(0.1) == analyze_pilot(p).difference
    rows = {(g.scope, g.staff_id, g.shift_id): g for g in report.groups}
    staff = rows[("staff", "s1", "")]
    assert (staff.removed_blocks, staff.removed_encounters, staff.remaining_encounters, staff.removed_weight) == (2, 30, 10, 0.75)
    assert staff.difference == -0.2 and staff.change == -0.3 and staff.opposite_sign
    shift = rows[("shift", "", "am")]
    assert shift.removed_blocks == 2 and shift.difference == -0.6 and shift.change == -0.7
    assert rows[("block", "s1", "am")].difference == -0.4
    assert rows[("shift", "", "pm")].difference == pytest.approx(1 / 3)
    assert report.summaries[0].opposite_sign_count == 1
    assert report.summaries[1].max_absolute_change == 0.7
    assert p.model_dump() == before
    # Non-delivery is retained in the assigned arm; changing delivery alone cannot improve the result.
    for row in p.assignments:
        row.delivered = True
    assert analyze_sensitivity(p) == report
    p.assignments.reverse()
    assert analyze_sensitivity(p) == report


def test_single_group_and_exact_zero_are_distinguished_from_opposite_signs():
    p = pilot(single=True)
    report = analyze_sensitivity(p)
    assert len(report.groups) == 3
    assert all(g.remaining_encounters == 0 and g.difference is None and g.change is None and g.opposite_sign is None for g in report.groups)
    assert all(s.estimable == 0 and s.minimum is None and s.max_absolute_change is None for s in report.summaries)
    p = pilot()
    for row in p.assignments:
        row.purchased = False
    report = analyze_sensitivity(p)
    assert report.difference == 0
    assert all(g.difference == 0 and g.change == 0 and g.opposite_sign is False for g in report.groups)


@pytest.mark.parametrize("field,value", [("enrolled", None), ("enrolled", False), ("purchased", None), ("delivered", None)])
def test_missing_or_unused_encounters_reject_the_whole_report(field, value):
    p = pilot(); setattr(p.assignments[0], field, value)
    with pytest.raises(ValueError, match="every planned encounter"):
        analyze_sensitivity(p)


def test_open_pilots_do_not_allow_repeated_interim_checks():
    p = pilot(); p.finalized_at = ""
    with pytest.raises(ValueError, match="Close and lock"):
        analyze_sensitivity(p)


@pytest.mark.parametrize("corrupt", [
    lambda p: p.assignments.pop(),
    lambda p: p.assignments.append(p.assignments[0]),
    lambda p: setattr(p.assignments[0], "staff_id", "other"),
    lambda p: setattr(p.assignments[0], "sequence", 999),
    lambda p: setattr(p.assignments[0], "arm", "B" if p.assignments[0].arm == "A" else "A"),
])
def test_saved_assignment_design_mismatch_is_rejected(corrupt):
    p = pilot(); corrupt(p)
    with pytest.raises(ValueError, match="fixed pilot design"):
        analyze_sensitivity(p)


def test_seeded_binary_outcomes_match_direct_balanced_arm_counts_and_sign_symmetry():
    rng = random.Random(71)
    for _ in range(40):
        p = pilot()
        for row in p.assignments:
            row.purchased = rng.choice([True, False])
        result = analyze_sensitivity(p)
        for g in result.groups:
            remaining = [r for r in p.assignments if not (
                (g.scope == "staff" and r.staff_id == g.staff_id) or (g.scope == "shift" and r.shift_id == g.shift_id) or
                (g.scope == "block" and (r.staff_id, r.shift_id) == (g.staff_id, g.shift_id)))]
            a = [r for r in remaining if r.arm == "A"]; b = [r for r in remaining if r.arm == "B"]
            expected = sum(r.purchased for r in b) / len(b) - sum(r.purchased for r in a) / len(a)
            assert g.difference == pytest.approx(expected)
            assert -1 <= g.difference <= 1 and abs(g.change) <= 2
        for row in p.assignments:
            row.purchased = not row.purchased
        flipped = analyze_sensitivity(p)
        assert flipped.difference == -result.difference
        assert [g.difference for g in flipped.groups] == [-g.difference for g in result.groups]
        assert [g.opposite_sign for g in flipped.groups] == [g.opposite_sign for g in result.groups]


def test_export_preserves_all_scopes_snapshot_proportions_and_unavailable_values():
    p = pilot(); p.product.sku = "=SKU"
    report = analyze_sensitivity(p)
    rows = list(csv.DictReader(io.StringIO(sensitivity_csv(report))))
    assert len(rows) == 7 and {r["scope"] for r in rows} == {"staff", "shift", "block"}
    assert rows[0]["revision"] == "2" and rows[0]["target_sku"] == "'=SKU"
    assert rows[0]["difference_unit"] == "proportion" and "Descriptive" in rows[0]["interpretation"]
    assert rows[0]["full_difference"] == "0.1" and rows[0]["difference"] == "-0.2" and rows[0]["opposite_sign"] == "1"
    empty = list(csv.DictReader(io.StringIO(sensitivity_csv(analyze_sensitivity(pilot(single=True))))))
    assert all(r["difference"] == r["change"] == r["opposite_sign"] == "" for r in empty)
