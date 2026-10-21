import csv
import io

from store_emulator.domain.field_observations import ObservationImportAudit, ObservationImportRecord
from store_emulator.domain.field_pilot import FieldPilot, PilotRequest
from store_emulator.domain.staff_pitch import PitchProduct, PitchVariant
from store_emulator.engine.marketing.field_observations import import_history_csv, preview_observations
from store_emulator.engine.marketing.field_pilot import allocate_pilot, observations_csv, parse_observations


def pilot():
    design = PilotRequest(name="Tea", eligibility="Each shopper once", outcome_window="Same visit",
                          blocks=[{"staff_id": "s1", "shift_id": "am", "encounters": 40}])
    return FieldPilot(pilot_id="pilot_test", pitch_id="pit_test", created_at="now", updated_at="now", design=design,
                      product=PitchProduct(sku="tea", name="Tea", price=1, currency="USD"),
                      variants=(PitchVariant(name="A", script="Hello"), PitchVariant(name="B", script="Welcome")),
                      context="Tea aisle", product_facts="", assignments=allocate_pilot("pilot_test", design))


def test_diff_keeps_unknown_false_corrections_and_enrollment_removal_distinct():
    p = pilot()
    p.assignments[0].enrolled = True
    p.assignments[0].delivered = False
    p.assignments[0].purchased = True
    p.assignments[1].enrolled = True
    p.assignments[1].purchased = False
    after = [a.model_copy(deep=True) for a in p.assignments]
    after[0].enrolled = False; after[0].delivered = None; after[0].purchased = None
    after[1].purchased = True; after[1].delivered = False
    after[2].enrolled = False
    diff = preview_observations(p, after, b"source")
    assert diff.summary.model_dump() == {"changed_assignments": 3, "changed_fields": 6, "new_values": 2,
                                         "corrected_values": 2, "cleared_values": 2, "removed_enrollments": 1,
                                         "purchase_reversals": 1}
    assert diff.changes[1].before is False and diff.changes[1].after is None
    assert p.assignments[0].enrolled and p.assignments[0].purchased


def test_review_binding_and_semantic_noop_with_reordered_csv_rows():
    p = pilot()
    data = observations_csv(p).encode()
    original = preview_observations(p, parse_observations(data, p), data)
    rows = list(csv.reader(io.StringIO(data.decode())))
    out = io.StringIO(); writer = csv.writer(out); writer.writerow(rows[0]); writer.writerows(reversed(rows[1:]))
    reordered = out.getvalue().encode()
    again = preview_observations(p, parse_observations(reordered, p), reordered)
    assert not original.changes and not again.changes
    assert original.review_token != again.review_token
    p.revision += 1
    assert preview_observations(p, p.assignments, data).review_token != original.review_token
    p.revision = 0; p.assignments[0].enrolled = False
    assert preview_observations(p, p.assignments, data).review_token != original.review_token
    p = pilot(); p.pilot_id = "pilot_other"
    assert preview_observations(p, p.assignments, data).review_token != original.review_token


def test_csv_history_preserves_boolean_states_and_neutralizes_formula_reasons():
    p = pilot(); after = [a.model_copy() for a in p.assignments]; after[0].enrolled = False
    preview = preview_observations(p, after, b"source")
    record = ObservationImportRecord(revision=1, imported_at="now", reason="  =HYPERLINK(\"bad\")\ncorrection",
                                     source_sha256="abc", summary=preview.summary)
    rows = list(csv.DictReader(io.StringIO(import_history_csv([ObservationImportAudit(record=record, changes=preview.changes)]))))
    assert len(rows) == 1
    assert rows[0]["before"] == "" and rows[0]["after"] == "0"
    assert rows[0]["reason"].startswith("'  =") and "\ncorrection" in rows[0]["reason"]
