"""Review recorded time for every assigned encounter; never impute missing duration."""

import csv
import hashlib
import io
import re
from decimal import Decimal
from fractions import Fraction

from store_emulator.domain.field_pilot import FieldPilot, PilotAssignment
from store_emulator.domain.field_timing import PilotTimingReport, TimingArm, TimingBlock, TimingRow
from store_emulator.domain.staff_pitch import Arm
from store_emulator.engine.marketing.field_pilot import allocate_pilot

COLUMNS = ["pilot_id", "assignment_id", "staff_seconds"]


def validate_timing_pilot(pilot: FieldPilot) -> None:
    if not pilot.finalized_at:
        raise ValueError("Close the completed fixed pilot before reviewing staff time")

    def identity(row: PilotAssignment) -> tuple[str, str, str, int, str]:
        return row.assignment_id, row.staff_id, row.shift_id, row.sequence, row.arm

    if sorted(map(identity, pilot.assignments)) != sorted(map(identity, allocate_pilot(pilot.pilot_id, pilot.design))):
        raise ValueError("Saved assignments do not match the fixed pilot design")
    if any(r.enrolled is not True or r.delivered is None or r.purchased is None for r in pilot.assignments):
        raise ValueError("Staff time review requires every planned encounter and complete purchase and delivery records")


def timing_template(pilot: FieldPilot) -> str:
    validate_timing_pilot(pilot)
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(COLUMNS)
    writer.writerows((pilot.pilot_id, row.assignment_id, "") for row in pilot.assignments)
    return out.getvalue()


def review_timing(pilot: FieldPilot, data: bytes) -> PilotTimingReport:
    validate_timing_pilot(pilot)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Staff time CSV exceeds 2 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 CSV") from exc
    expected = {row.assignment_id for row in pilot.assignments}
    times: dict[str, int | None] = {}
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader, list[str]())
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise ValueError("Use pilot_id, assignment_id and staff_seconds exactly once")
        for line, values in enumerate(reader, start=2):
            if line > 10001:
                raise ValueError("Staff time CSV exceeds 10,000 rows")
            if len(values) != len(header):
                raise ValueError(f"Row {line}: wrong number of columns")
            row = dict(zip(header, values, strict=True))
            if row["pilot_id"] != pilot.pilot_id or row["assignment_id"] not in expected:
                raise ValueError(f"Row {line}: pilot or assignment ID does not match the fixed plan")
            aid = row["assignment_id"]
            if aid in times:
                raise ValueError(f"Row {line}: duplicate assignment ID; record one total staff time per encounter")
            raw = row["staff_seconds"]
            if raw == "":
                times[aid] = None
            else:
                if len(raw) > 8 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,3})?", raw) or Decimal(raw) > 3600:
                    raise ValueError(f"Row {line}: staff_seconds must be blank or a decimal from 0 to 3600 with up to three decimal places")
                times[aid] = int(Decimal(raw) * 1000)
    except csv.Error as exc:
        raise ValueError("Malformed staff time CSV; keep quoted fields intact") from exc
    if not times:
        raise ValueError("Staff time CSV must contain at least one assignment row")
    complete = all(times.get(aid) is not None for aid in expected)

    def summary(arm: Arm) -> TimingArm:
        assigned = [r for r in pilot.assignments if r.arm == arm]
        recorded = [value for r in assigned if (value := times.get(r.assignment_id)) is not None]
        return TimingArm(arm=arm, planned=len(assigned), timed=len(recorded),
                         mean_seconds=float(Fraction(sum(recorded), len(assigned) * 1000)) if complete else None,
                         max_seconds=max(recorded) / 1000 if complete else None)

    a, b = summary("A"), summary("B")
    # The full balanced plan's pooled mean equals its planned-count weighted block mean.
    delta = Fraction(sum((times[r.assignment_id] or 0) * (1 if r.arm == "B" else -1) for r in pilot.assignments), len(expected) * 500) if complete else None
    return PilotTimingReport(pilot_id=pilot.pilot_id, revision=pilot.revision, source_sha256=hashlib.sha256(data).hexdigest(),
        source_rows=len(times), complete=complete, planned=len(expected), timed=sum(v is not None for v in times.values()),
        a=a, b=b, difference_seconds=float(delta) if delta is not None else None,
        blocks=[TimingBlock(staff_id=block.staff_id, shift_id=block.shift_id, planned=block.encounters,
                    timed=sum(times.get(r.assignment_id) is not None for r in pilot.assignments if r.staff_id == block.staff_id and r.shift_id == block.shift_id))
                for block in pilot.design.blocks],
        rows=[TimingRow(assignment_id=r.assignment_id, staff_id=r.staff_id, shift_id=r.shift_id, arm=r.arm,
                       staff_seconds=value / 1000 if (value := times.get(r.assignment_id)) is not None else None) for r in pilot.assignments],
        notes=[
            "Uploaded observations are supplied by the operator and are not independently verified. Record total active staff time per assigned eligible encounter under the same timing protocol in both arms, including refusals and non-delivery. Do not time only buyers or delivered scripts.",
            "Blank or absent rows are unknown, never zero. Enter 0 only for a verified zero duration. Means, maxima and the B-minus-A difference are withheld until every fixed assignment has a duration. Staff and shift coverage is shown to help locate missing records.",
            "Each assignment remains in its original arm. For the complete balanced plan, pooled means equal block means weighted by planned encounters. No rows are dropped by delivery or purchase; no significance test, confidence interval or staff ranking is produced.",
            "Time uses seconds with up to three decimal places, from 0 to 3600 per encounter. Means can be fractional. The cost scenario accepts whole-second assumptions; choose and document those assumptions separately without treating rounded values as exact measurements.",
            "This review is read-only and is not retained in the project. Export the audit with its source SHA-256 and pilot revision. It does not prove causal effects, staffing capacity or future costs, and does not correct repeated shoppers, timing error, clustering or confounding.",
        ])


def timing_csv(report: PilotTimingReport) -> str:
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(["method", "pilot_id", "revision", "source_sha256", "complete", "assignment_id", "staff_id", "shift_id", "arm", "staff_seconds", "mean_a_seconds", "mean_b_seconds", "difference_seconds"])
    for row in report.rows:
        values: list[str | int | float | None] = [report.method, report.pilot_id, report.revision, report.source_sha256,
            int(report.complete), row.assignment_id, row.staff_id, row.shift_id, row.arm, row.staff_seconds,
            report.a.mean_seconds, report.b.mean_seconds, report.difference_seconds]
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v for v in values])
    return out.getvalue()
