"""Pure observation diffs; revisions and file content bind a review to one proposed replacement."""

import csv
import hashlib
import io

from store_emulator.domain.field_observations import (
    ObservationChange, ObservationDiff, ObservationField, ObservationImportAudit, ObservationPreview,
)
from store_emulator.domain.field_pilot import FieldPilot, PilotAssignment
from store_emulator.engine.marketing.field_pilot import observations_csv

FIELDS: tuple[ObservationField, ...] = ("enrolled", "delivered", "purchased")


def preview_observations(pilot: FieldPilot, assignments: list[PilotAssignment], data: bytes) -> ObservationPreview:
    """Assignments must first pass the full-sheet parser; its output uses the saved order."""
    changes: list[ObservationChange] = []
    for before, after in zip(pilot.assignments, assignments, strict=True):
        for field, old, new in zip(FIELDS, (before.enrolled, before.delivered, before.purchased),
                                   (after.enrolled, after.delivered, after.purchased), strict=True):
            if old is not new:
                changes.append(ObservationChange(assignment_id=before.assignment_id, staff_id=before.staff_id,
                                                shift_id=before.shift_id, sequence=before.sequence, arm=before.arm,
                                                field=field, before=old, after=new))
    summary = ObservationDiff(
        changed_assignments=len({c.assignment_id for c in changes}), changed_fields=len(changes),
        new_values=sum(c.before is None for c in changes),
        corrected_values=sum(c.before is not None and c.after is not None for c in changes),
        cleared_values=sum(c.after is None for c in changes),
        removed_enrollments=sum(c.field == "enrolled" and c.before is True for c in changes),
        purchase_reversals=sum(c.field == "purchased" and c.before is not None and c.after is not None for c in changes),
    )
    # This is a content/revision check, not authentication or proof that a human reviewed the file.
    token = hashlib.sha256(f"{pilot.pilot_id}:{pilot.revision}:".encode()
                           + hashlib.sha256(observations_csv(pilot).encode()).digest()
                           + hashlib.sha256(data).digest()).hexdigest()
    return ObservationPreview(pilot_id=pilot.pilot_id, revision=pilot.revision, review_token=token,
                              summary=summary, changes=changes)


def import_history_csv(audits: list[ObservationImportAudit]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["revision", "imported_at", "reason", "source_sha256", "assignment_id", "staff_id", "shift_id",
                     "sequence", "arm", "field", "before", "after"])
    for audit in audits:
        record = audit.record
        reason = record.reason
        if reason.lstrip().startswith(("=", "+", "-", "@")):
            reason = "'" + reason
        for c in audit.changes:
            writer.writerow([record.revision, record.imported_at, reason, record.source_sha256, c.assignment_id,
                             c.staff_id, c.shift_id, c.sequence, c.arm, c.field,
                             "" if c.before is None else int(c.before), "" if c.after is None else int(c.after)])
    return out.getvalue()
