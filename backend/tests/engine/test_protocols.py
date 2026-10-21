import csv
import io
from datetime import datetime, timezone

from store_emulator.domain.protocols import ProtocolLedger, ProtocolPlan
from store_emulator.engine.analysis.protocols import protocol_changes_csv, record_revision, review_protocol

PID = "proj_test"
ID = "protocol_" + "a" * 32
NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


def plan(**changes):
    return ProtocolPlan.model_validate({"title": "Shelf sign study", "evidence_type": "synthetic", "question": "Does the sign change selection?",
        "population": "Saved persona cohort", "design": "Paired price by sign", "primary_outcome": "Any purchase per visit", "analysis_unit": "Shopper",
        "planned_sample_size": 60, "exclusions_and_missing": "Report missing; no imputation", "stopping_rule": "One fixed sample, no interim selection",
        "analysis_plan": "Paired contrasts; three-comparison adjustment; exploratory synthetic inference", **changes})


def ledger():
    revision = record_revision(PID, ID, plan(), "not_collected", NOW, "Initial plan", None)
    return ProtocolLedger(format_version="protocol-ledger-v1", project_id=PID, protocol_id=ID, revisions=[revision])


def test_records_full_snapshots_hashes_and_calculated_amendment_differences():
    data = ledger(); original = data.revisions[0].model_dump_json()
    data.revisions.append(record_revision(PID, ID, plan(planned_sample_size=40, primary_outcome="Items per visit"), "results_seen", NOW, "Exploratory follow-up", data.revisions[-1]))
    view = review_protocol(data)
    assert data.revisions[0].model_dump_json() == original
    assert view.planned_sample_delta == -20 and view.revisions_with_results_seen == 1
    assert view.changed_from_original == ["primary_outcome", "planned_sample_size"]
    assert [(c.field, c.before, c.after) for c in view.reviews[1].changes] == [("primary_outcome", "Any purchase per visit", "Items per visit"), ("planned_sample_size", 60, 40), ("data_stage", "not_collected", "results_seen")]
    restored = ProtocolLedger.model_validate_json(data.model_dump_json())
    assert review_protocol(restored) == view
    exported = list(csv.DictReader(io.StringIO(protocol_changes_csv(view))))
    assert exported[-1]["after"] == "results_seen" and all(r["head_sha256"] == view.head_sha256 for r in exported)


import pytest
from pydantic import ValidationError

from store_emulator.domain.protocols import AmendProtocol, CreateProtocol
from store_emulator.engine.analysis.protocols import revision_digest


@pytest.mark.parametrize(("key", "value"), [("title", ""), ("title", "   "), ("title", "x" * 121), ("question", "x" * 1501),
    ("question", "\x00hidden"), ("analysis_plan", "zero\u200bwidth"), ("evidence_type", "mixed"),
    ("planned_sample_size", 0), ("planned_sample_size", -1), ("planned_sample_size", 1_000_001), ("planned_sample_size", True),
    ("planned_sample_size", "60"), ("planned_sample_size", 1.5), ("planned_sample_size", float("nan")), ("planned_sample_size", float("inf"))])
def test_plan_boundaries(key, value):
    with pytest.raises(ValidationError): plan(**{key: value})


def test_unknown_missing_fields_invalid_ids_and_reasons():
    raw = plan().model_dump()
    with pytest.raises(ValidationError): ProtocolPlan.model_validate({**raw, "extra": "ignored?"})
    del raw["primary_outcome"]
    with pytest.raises(ValidationError): ProtocolPlan.model_validate(raw)
    for token in ["", "a" * 31, "a" * 33, "A" * 32, "../unsafe"]:
        with pytest.raises(ValidationError): CreateProtocol(request_id=token, plan=plan(), data_stage="not_collected")
    for reason in ["", " \n\t", "x" * 1001, "hidden\x00"]:
        with pytest.raises(ValidationError): AmendProtocol(expected_head="a" * 64, plan=plan(), data_stage="results_seen", reason=reason)


def test_min_max_sample_unicode_and_multiline_plan_round_trip():
    for count in [1, 1_000_000]:
        p = plan(planned_sample_size=count, title="연구 🧪", question="αβ\n고객\t계획" + "茶" * 1490)
        data = ledger(); data.revisions[0] = record_revision(PID, ID, p, "not_collected", NOW, "Initial plan", None)
        restored = ProtocolLedger.model_validate_json(data.model_dump_json())
        assert review_protocol(restored).planned_sample_delta == 0
    p = plan(); first = record_revision(PID, ID, p, "not_collected", NOW, "Initial plan", None)
    p.question = "Changed caller object"
    assert first.plan.question != p.question


def test_noop_stage_reversal_and_naive_clock_rejected():
    previous = ledger().revisions[0]
    with pytest.raises(ValueError, match="No plan"):
        record_revision(PID, ID, previous.plan, previous.data_stage, NOW, "Only reason changed", previous)
    later = record_revision(PID, ID, previous.plan, "results_seen", NOW, "Results available", previous)
    for stage in ["not_collected", "collected_unseen"]:
        with pytest.raises(ValueError, match="backward"):
            record_revision(PID, ID, plan(title="Another study"), stage, NOW, "Cannot erase visibility", later)
    with pytest.raises(ValidationError): record_revision(PID, ID, plan(), "not_collected", NOW.replace(tzinfo=None), "Initial plan", None)


@pytest.mark.parametrize("kind", ["plan", "hash", "parent", "sequence", "identity", "stage"])
def test_hash_sequence_and_stage_corruption_detected(kind):
    data = ledger(); data.revisions.append(record_revision(PID, ID, plan(planned_sample_size=80), "results_seen", NOW, "Review", data.revisions[-1]))
    if kind == "plan": data.revisions[0].plan.question = "Edited old hypothesis"
    elif kind == "hash": data.revisions[-1].sha256 = "b" * 64
    elif kind == "parent": data.revisions[-1].previous_sha256 = None
    elif kind == "sequence": data.revisions[-1].revision = 3
    elif kind == "identity": data.project_id = "another_project"
    else:
        data.revisions[0].data_stage = "results_seen"; data.revisions[-1].data_stage = "not_collected"
        data.revisions[0].sha256 = revision_digest(PID, ID, data.revisions[0]); data.revisions[-1].previous_sha256 = data.revisions[0].sha256
        data.revisions[-1].sha256 = revision_digest(PID, ID, data.revisions[-1])
    with pytest.raises(ValueError): review_protocol(data)


def test_returns_to_original_keep_intermediate_changes_and_stage_only_amendments():
    data = ledger()
    data.revisions.append(record_revision(PID, ID, plan(planned_sample_size=1), "collected_unseen", NOW, "Reduced target", data.revisions[-1]))
    data.revisions.append(record_revision(PID, ID, plan(), "collected_unseen", NOW, "Restored target", data.revisions[-1]))
    data.revisions.append(record_revision(PID, ID, plan(), "results_seen", NOW, "Results opened", data.revisions[-1]))
    r = review_protocol(data)
    assert r.changed_from_original == [] and r.planned_sample_delta == 0
    assert r.reviews[-1].changes[0].field == "data_stage" and len(r.reviews[-1].changes) == 1
    assert r.reviews[1].changes[0].before == 60 and r.reviews[2].changes[0].before == 1


@pytest.mark.parametrize("changes", [{"analysis_unit": "Store"}, {"evidence_type": "observed"}])
def test_sample_delta_withheld_when_units_or_evidence_are_not_comparable(changes):
    data = ledger(); data.revisions.append(record_revision(PID, ID, plan(planned_sample_size=80, **changes), "collected_unseen", NOW, "Different measurement scope", data.revisions[-1]))
    assert review_protocol(data).planned_sample_delta is None


def test_csv_untrusted_text_and_numeric_values_remain_distinct():
    data = ledger(); data.revisions.append(record_revision(PID, ID, plan(title="=HYPERLINK(1)", planned_sample_size=1), "results_seen", NOW, "@review", data.revisions[-1]))
    rows = list(csv.DictReader(io.StringIO(protocol_changes_csv(review_protocol(data)))))
    title = next(r for r in rows if r["revision"] == "2" and r["field"] == "title")
    count = next(r for r in rows if r["revision"] == "2" and r["field"] == "planned_sample_size")
    assert title["after"].startswith("'=") and title["reason"] == "'@review"
    assert count["before"] == "60" and count["after"] == "1"
