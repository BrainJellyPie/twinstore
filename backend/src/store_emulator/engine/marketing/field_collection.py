"""Collection checks use outcome availability, never the yes/no purchase values."""

import csv
import io

from store_emulator.domain.field_collection import (
    CollectionBlock, CollectionCounts, CollectionGuidance, CollectionIssue, CollectionTask, PilotCollectionReport,
)
from store_emulator.domain.field_pilot import FieldPilot, PilotAssignment


def _counts(rows: list[PilotAssignment]) -> CollectionCounts:
    enrolled = [r for r in rows if r.enrolled is True]
    missing_purchase = sum(r.purchased is None for r in enrolled)
    missing_delivery = sum(r.delivered is None for r in enrolled)
    known_delivery = len(enrolled) - missing_delivery
    not_delivered = sum(r.delivered is False for r in enrolled)
    return CollectionCounts(
        planned=len(rows), enrolled=len(enrolled), unused=sum(r.enrolled is False for r in rows),
        unrecorded=sum(r.enrolled is None for r in rows),
        complete_enrolled=sum(r.purchased is not None and r.delivered is not None for r in enrolled),
        missing_purchase=missing_purchase, missing_delivery=missing_delivery,
        known_delivery=known_delivery, not_delivered=not_delivered,
        purchase_missing_rate=missing_purchase / len(enrolled) if enrolled else None,
        non_delivery_rate=not_delivered / known_delivery if known_delivery else None,
    )


def check_collection(pilot: FieldPilot) -> PilotCollectionReport:
    grouped: dict[tuple[str, str], list[PilotAssignment]] = {}
    for row in pilot.assignments:
        grouped.setdefault((row.staff_id, row.shift_id), []).append(row)
    blocks: list[CollectionBlock] = []
    tasks: list[CollectionTask] = []
    for design in pilot.design.blocks:
        rows = sorted(grouped[(design.staff_id, design.shift_id)], key=lambda row: row.sequence)
        last_recorded = max((r.sequence for r in rows if r.enrolled is not None), default=0)
        last_enrolled = max((r.sequence for r in rows if r.enrolled is True), default=0)
        gaps = 0
        unused_before = 0
        for row in rows:
            issues: list[CollectionIssue] = []
            if row.enrolled is True:
                if row.purchased is None:
                    issues.append("purchase_unknown")
                if row.delivered is None:
                    issues.append("delivery_unknown")
            elif row.enrolled is None and row.sequence < last_recorded:
                issues.append("enrollment_gap")
                gaps += 1
            elif row.enrolled is False and row.sequence < last_enrolled:
                issues.append("unused_before_enrolled")
                unused_before += 1
            if issues:
                tasks.append(CollectionTask(assignment_id=row.assignment_id, staff_id=row.staff_id,
                                            shift_id=row.shift_id, sequence=row.sequence, arm=row.arm, issues=issues))
        counts = _counts(rows)
        a, b = _counts([r for r in rows if r.arm == "A"]), _counts([r for r in rows if r.arm == "B"])
        blocks.append(CollectionBlock(
            staff_id=design.staff_id, shift_id=design.shift_id, counts=counts, a=a, b=b,
            last_recorded_sequence=last_recorded or None, recording_gaps=gaps, unused_before_enrolled=unused_before,
            unrecorded_tail=counts.unrecorded - gaps,
            purchase_missing_gap=b.purchase_missing_rate - a.purchase_missing_rate
            if b.purchase_missing_rate is not None and a.purchase_missing_rate is not None else None,
        ))
    counts = _counts(pilot.assignments)
    can_finalize = counts.unrecorded == 0 and counts.complete_enrolled + counts.unused == counts.planned
    return PilotCollectionReport(
        pilot_id=pilot.pilot_id, name=pilot.design.name, revision=pilot.revision, updated_at=pilot.updated_at,
        finalized_at=pilot.finalized_at, outcome_window=pilot.design.outcome_window, counts=counts,
        recording_gaps=sum(b.recording_gaps for b in blocks), unused_before_enrolled=sum(b.unused_before_enrolled for b in blocks),
        unrecorded_tail=sum(b.unrecorded_tail for b in blocks), can_finalize=can_finalize,
        target_completed=can_finalize and counts.enrolled == counts.planned, blocks=blocks, tasks=tasks,
        guidance=[
            CollectionGuidance(issue="purchase_unknown", title="Purchase outcome unknown",
                               action="Check source records after the saved outcome window. Keep the outcome unknown until verified; never fill a missing purchase with no."),
            CollectionGuidance(issue="delivery_unknown", title="Script delivery unknown",
                               action="Verify whether the assigned script was delivered. Record refusals or non-delivery as no and retain the encounter in its assigned arm."),
            CollectionGuidance(issue="enrollment_gap", title="Enrollment record gap",
                               action="Confirm the status of this blank slot before a later recorded slot. Check records; do not assume that a customer was enrolled or move assignments."),
            CollectionGuidance(issue="unused_before_enrolled", title="Unused slot before later enrollment",
                               action="Review why this slot was unused before a later enrolled encounter. Correct only a verified recording error; do not relabel unused slots to reach the target."),
        ],
        notes=[
            "This report uses outcome availability only. Switching a recorded purchase between yes and no does not change these checks. It provides no purchase counts, conversion estimates, winners or significance tests.",
            "Unrecorded tail slots follow the last recorded enrollment status in each staff/shift. They may be future assignments or unentered records, not known missing customers. A recording gap is a prompt to check records, not proof of skipped assignment or misconduct.",
            "Purchase missingness uses enrolled encounters as its denominator; non-delivery uses enrolled encounters with known delivery status. An empty denominator is unknown. B-minus-A missingness differences describe record completeness, not treatment effects or statistical evidence of imbalance.",
            "Non-delivery includes refusal and is not automatically an error. Keep these encounters in their original arm. Staff/shift comparisons cannot establish a staff performance effect, and blocking does not remove unmeasured clustering or confounding.",
            "No encounter timestamps are available, so tasks are not classified as overdue. Apply verified changes through the full observation-sheet review. Never fabricate outcomes, omit assigned customers, resize the plan or repeatedly test for a preferred result.",
            "All recorded slots and enrolled outcomes must be settled before closure. Sequence-review flags do not prove the protocol was followed and do not independently block closure. A closed pilot stays locked, and any unused slot prevents confirmatory inference.",
        ],
    )


def collection_tasks_csv(report: PilotCollectionReport) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["pilot_id", "revision", "updated_at", "finalized_at", "staff_id", "shift_id", "sequence",
                     "assignment_id", "arm", "issue", "action"])
    actions = {g.issue: g.action for g in report.guidance}
    for task in report.tasks:
        for issue in task.issues:
            writer.writerow([report.pilot_id, report.revision, report.updated_at, report.finalized_at,
                             task.staff_id, task.shift_id, task.sequence, task.assignment_id, task.arm, issue, actions[issue]])
    return out.getvalue()
