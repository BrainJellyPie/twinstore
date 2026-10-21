import csv
import io

from store_emulator.domain.field_pilot import FieldPilot, PilotRequest
from store_emulator.domain.staff_pitch import PitchProduct, PitchVariant
from store_emulator.engine.marketing.field_collection import check_collection, collection_tasks_csv
from store_emulator.engine.marketing.field_pilot import allocate_pilot, analyze_pilot


def pilot():
    design = PilotRequest(name="Collection", eligibility="Each customer once", outcome_window="Same visit",
                          blocks=[{"staff_id": "s1", "shift_id": "am", "encounters": 20},
                                  {"staff_id": "s1", "shift_id": "pm", "encounters": 20}])
    return FieldPilot(pilot_id="pilot_test", pitch_id="pit_test", created_at="now", updated_at="now", revision=7, design=design,
                      product=PitchProduct(sku="tea", name="Tea", price=1, currency="USD"),
                      variants=(PitchVariant(name="A", script="Hello"), PitchVariant(name="B", script="Welcome")),
                      context="Tea aisle", product_facts="", assignments=allocate_pilot("pilot_test", design))


def test_unused_future_capacity_is_not_reported_as_missing_customers():
    report = check_collection(pilot())
    assert report.unrecorded_tail == 40 and report.recording_gaps == 0 and report.tasks == []
    assert report.counts.enrolled == report.counts.missing_purchase == 0
    assert report.counts.purchase_missing_rate is None and report.counts.non_delivery_rate is None
    assert not report.can_finalize and not report.target_completed
    assert all(b.last_recorded_sequence is None and b.purchase_missing_gap is None for b in report.blocks)


def test_followup_separates_unknown_outcomes_recording_gaps_and_unused_slots():
    p = pilot(); a = p.assignments
    a[0].enrolled = True; a[0].delivered = False
    a[2].enrolled = False
    a[3].enrolled = True; a[3].purchased = False
    a[20].enrolled = True; a[20].delivered = True; a[20].purchased = True
    report = check_collection(p)
    assert [(t.sequence, t.issues) for t in report.tasks] == [
        (1, ["purchase_unknown"]), (2, ["enrollment_gap"]), (3, ["unused_before_enrolled"]), (4, ["delivery_unknown"]),
    ]
    assert (report.counts.enrolled, report.counts.unused, report.counts.unrecorded) == (3, 1, 36)
    assert report.counts.complete_enrolled == 1 and report.counts.non_delivery_rate == 0.5
    assert (report.recording_gaps, report.unrecorded_tail, report.unused_before_enrolled) == (1, 35, 1)
    assert report.blocks[0].last_recorded_sequence == 4 and report.blocks[1].last_recorded_sequence == 1
    assert report.blocks[1].recording_gaps == 0
    shuffled = p.model_copy(deep=True); shuffled.assignments.reverse()
    assert check_collection(shuffled) == report


def test_two_missing_fields_share_one_assignment_and_refusal_is_not_a_correction_task():
    p = pilot(); p.assignments[0].enrolled = True
    report = check_collection(p)
    assert len(report.tasks) == 1 and report.tasks[0].issues == ["purchase_unknown", "delivery_unknown"]
    assert report.counts.purchase_missing_rate == 1 and report.counts.non_delivery_rate is None
    p.assignments[0].purchased = False; p.assignments[0].delivered = False
    report = check_collection(p)
    assert report.tasks == [] and report.counts.not_delivered == 1 and report.counts.non_delivery_rate == 1
    assert report.counts.complete_enrolled == 1


def test_rate_denominators_remain_within_their_staff_shift_and_arm():
    p = pilot()
    for row in p.assignments[:20]:
        row.enrolled = True; row.delivered = False
        row.purchased = None if row.arm == "A" else False
    report = check_collection(p)
    am, pm = report.blocks
    assert am.a.missing_purchase == am.a.enrolled == 10
    assert am.b.missing_purchase == 0 and am.b.enrolled == 10
    assert am.purchase_missing_gap == -1 and am.counts.purchase_missing_rate == 0.5
    assert am.counts.non_delivery_rate == 1
    assert pm.a.purchase_missing_rate is None and pm.purchase_missing_gap is None
    assert pm.recording_gaps == 0 and pm.unrecorded_tail == 20


def test_purchase_values_cannot_change_collection_report_or_checklist():
    p = pilot()
    for row in p.assignments:
        row.enrolled = True; row.delivered = row.sequence % 2 == 0; row.purchased = row.arm == "A"
    p.assignments[0].purchased = None
    before = check_collection(p)
    for row in p.assignments:
        if row.purchased is not None:
            row.purchased = not row.purchased
    after = check_collection(p)
    assert before.model_dump() == after.model_dump()
    assert collection_tasks_csv(before) == collection_tasks_csv(after)


def test_closure_readiness_matches_existing_rules_and_keeps_sequence_flags_after_close():
    p = pilot()
    for row in p.assignments:
        row.enrolled = True; row.delivered = False; row.purchased = False
    assert check_collection(p).can_finalize == analyze_pilot(p).can_finalize
    assert check_collection(p).target_completed
    p.assignments[0].enrolled = False; p.assignments[0].delivered = None; p.assignments[0].purchased = None
    p.finalized_at = "closed"
    report = check_collection(p)
    assert report.can_finalize == analyze_pilot(p).can_finalize
    assert not report.target_completed and report.unused_before_enrolled == 1
    assert report.tasks[0].issues == ["unused_before_enrolled"] and report.finalized_at == "closed"


def test_csv_has_one_row_per_check_and_snapshot_metadata_without_purchase_values():
    p = pilot()
    assert list(csv.DictReader(io.StringIO(collection_tasks_csv(check_collection(p))))) == []
    p.assignments[0].enrolled = True
    rows = list(csv.DictReader(io.StringIO(collection_tasks_csv(check_collection(p)))))
    assert len(rows) == 2 and {r["issue"] for r in rows} == {"purchase_unknown", "delivery_unknown"}
    assert all(r["revision"] == "7" and r["pilot_id"] == "pilot_test" and r["updated_at"] == "now" for r in rows)
    assert len({r["assignment_id"] for r in rows}) == 1
    assert "purchased" not in rows[0] and "purchases" not in rows[0]
