"""Balanced allocations, strict observation imports and fixed-sample conversion comparisons."""

import csv
import io
import math
import random
from datetime import date, datetime

from store_emulator.domain.field_pilot import (
    FieldPilot, PilotAnalysis, PilotArmSummary, PilotAssignment, PilotBlockSummary, PilotRequest,
)
from store_emulator.domain.staff_pitch import Arm
from store_emulator.domain.types import stable_seed

COLUMNS = ["pilot_id", "assignment_id", "staff_id", "shift_id", "sequence", "arm", "enrolled", "delivered", "purchased"]


def allocate_pilot(pilot_id: str, design: PilotRequest) -> list[PilotAssignment]:
    assignments: list[PilotAssignment] = []
    for i, block in enumerate(design.blocks):
        arms: list[Arm] = ["A", "B"] * (block.encounters // 2)
        random.Random(stable_seed("field-pilot-v1", design.seed, block.staff_id, block.shift_id)).shuffle(arms)
        assignments.extend(PilotAssignment(assignment_id=f"{pilot_id}_{i + 1}_{j + 1}", staff_id=block.staff_id,
                                           shift_id=block.shift_id, sequence=j + 1, arm=arm)
                           for j, arm in enumerate(arms))
    return assignments


def observations_csv(pilot: FieldPilot) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for a in pilot.assignments:
        writer.writerow([pilot.pilot_id, a.assignment_id, a.staff_id, a.shift_id, a.sequence, a.arm,
                         *["" if value is None else int(value) for value in (a.enrolled, a.delivered, a.purchased)]])
    return out.getvalue()


def parse_observations(data: bytes, pilot: FieldPilot) -> list[PilotAssignment]:
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Observation CSV exceeds 2 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 CSV") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    expected = {a.assignment_id: a for a in pilot.assignments}
    seen: dict[str, PilotAssignment] = {}
    try:
        header = next(reader, list[str]())
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise ValueError("Keep all original template columns exactly once")
        for line, values in enumerate(reader, start=2):
            if len(values) != len(header):
                raise ValueError(f"Row {line}: wrong number of columns")
            row = dict(zip(header, values, strict=True))
            aid = row["assignment_id"]
            if aid not in expected or aid in seen:
                raise ValueError(f"Row {line}: unknown or duplicate assignment ID")
            saved = expected[aid]
            immutable = {"pilot_id": pilot.pilot_id, "sequence": str(saved.sequence), "arm": saved.arm}
            reformatted = {"staff_id": saved.staff_id, "shift_id": saved.shift_id}
            if (any(row[key] != value for key, value in immutable.items())
                    or not all(_same_id(row[key], value) for key, value in reformatted.items())):
                raise ValueError(f"Row {line}: assigned pilot, staff, shift, sequence and arm cannot be changed")
            bits: dict[str, bool | None] = {}
            for key in ("enrolled", "delivered", "purchased"):
                value = row[key].strip()
                if value not in ("", "0", "1"):
                    raise ValueError(f"Row {line}: {key} must be 0, 1 or blank")
                bits[key] = None if value == "" else value == "1"
            if bits["enrolled"] is not True and (bits["delivered"] is not None or bits["purchased"] is not None):
                raise ValueError(f"Row {line}: only enrolled encounters can have delivery or purchase observations")
            seen[aid] = saved.model_copy(update=bits)
    except csv.Error as exc:
        raise ValueError("Malformed CSV; keep quoted fields intact") from exc
    if len(seen) != len(expected):
        raise ValueError("Upload the full assignment template, including blank and unused slots")
    return [seen[a.assignment_id] for a in pilot.assignments]


_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%d.%m.%Y", "%m/%d/%y", "%d/%m/%y", "%Y. %m. %d.",
                 "%Y.%m.%d")


def _dates(text: str) -> set[date]:
    found: set[date] = set()
    for fmt in _DATE_FORMATS:
        try:
            found.add(datetime.strptime(text, fmt).date())  # noqa: DTZ007 — a calendar date, no time of day
        except ValueError:
            continue
    return found


def _same_id(cell: str, saved: str) -> bool:
    """A staff or shift id as a spreadsheet saved it back: Excel drops leading zeros (007 → 7) and rewrites dates in
    the computer's format (2026-10-22 → 10/22/2026). The assignment id still pins the row, so those count as equal."""
    a, b = cell.strip(), saved.strip()
    if a == b:
        return True
    if a.isdigit() and b.isdigit():
        return int(a) == int(b)
    return bool(_dates(a) & _dates(b))


def _arm(rows: list[PilotAssignment], arm: Arm) -> PilotArmSummary:
    group = [a for a in rows if a.arm == arm]
    enrolled = [a for a in group if a.enrolled is True]
    observed = [a for a in enrolled if a.purchased is not None]
    purchases = sum(a.purchased is True for a in observed)
    missing = len(enrolled) - len(observed)
    return PilotArmSummary(
        arm=arm, planned=len(group), enrolled=len(enrolled), unused=sum(a.enrolled is False for a in group),
        unrecorded=sum(a.enrolled is None for a in group), observed=len(observed), purchases=purchases,
        missing_outcomes=missing, not_delivered=sum(a.delivered is False for a in enrolled),
        delivery_unknown=sum(a.delivered is None for a in enrolled),
        observed_rate=purchases / len(observed) if observed else None,
        missing_bound_low=purchases / len(enrolled) if enrolled else None,
        missing_bound_high=(purchases + missing) / len(enrolled) if enrolled else None,
    )


def analyze_pilot(pilot: FieldPilot) -> PilotAnalysis:
    a, b = _arm(pilot.assignments, "A"), _arm(pilot.assignments, "B")
    blocks: list[PilotBlockSummary] = []
    for block in pilot.design.blocks:
        rows = [row for row in pilot.assignments if (row.staff_id, row.shift_id) == (block.staff_id, block.shift_id)]
        ba, bb = _arm(rows, "A"), _arm(rows, "B")
        blocks.append(PilotBlockSummary(staff_id=block.staff_id, shift_id=block.shift_id, a=ba, b=bb,
                                       observed_diff=bb.observed_rate - ba.observed_rate
                                       if ba.observed_rate is not None and bb.observed_rate is not None else None))
    can_finalize = all(row.enrolled is False or (row.enrolled is True and row.purchased is not None
                                               and row.delivered is not None) for row in pilot.assignments)
    target_completed = can_finalize and a.enrolled + b.enrolled == len(pilot.assignments)
    ready = bool(pilot.finalized_at) and target_completed
    diff: float | None = None
    lo: float | None = None
    hi: float | None = None
    interpretation = "Collection is open. Complete the fixed plan before closing; no effect interval is shown during collection."
    if pilot.finalized_at and not target_completed:
        interpretation = "Closed below the planned sample target. Counts are descriptive; no confirmatory effect interval is reported."
    if ready:
        total = len(pilot.assignments)
        diff = sum((row.a.planned + row.b.planned) / total * (row.observed_diff or 0.0) for row in blocks)
        # Hoeffding bound for a weighted difference of independent bounded encounter outcomes.
        # Unlike a percentile bootstrap, it stays nonzero when all observed purchases are 0 or 1.
        sum_squared_weights = sum(((row.a.planned + row.b.planned) / total) ** 2
                                  * (1 / row.a.observed + 1 / row.b.observed) for row in blocks)
        radius = math.sqrt(math.log(2 / 0.05) / 2 * sum_squared_weights)
        lo, hi = max(-1.0, diff - radius), min(1.0, diff + radius)
        interpretation = ("The fixed-sample interval favors B on observed target-product conversion." if lo > 0 else
                          "The fixed-sample interval favors A on observed target-product conversion." if hi < 0 else
                          "The interval includes zero; the pilot does not resolve a conversion difference.")
    return PilotAnalysis(
        a=a, b=b, blocks=blocks, target_completed=target_completed, can_finalize=can_finalize,
        inference_ready=ready, difference=diff, ci_low=lo, ci_high=hi, interpretation=interpretation,
        notes=[
            "Observed field records only; synthetic shopper ratings are never counted as purchases.",
            "Use one next-in-sequence assignment per eligible encounter within its staff/shift block. Enroll before revealing the script. Do not skip an arm, reuse a customer, or change the offer.",
            "Enrolled customers remain in their assigned arm even when the script was not delivered or was refused (intention to treat). Unused planned slots are not customers and missing purchases are not zeros.",
            "Purchase means the target SKU was bought within the saved outcome window. Eligibility and outcome capture must be identical for both arms.",
            "During collection, observed rates use known outcomes only. Missing-outcome bounds show the enrolled-customer rate if all unknown outcomes were failures or successes; they are not confidence intervals.",
            "The final B-minus-A estimate weights staff/shift blocks by their precommitted planned counts. All planned encounters and outcomes are required for inference; an early close gives descriptive counts only.",
            "The 95% interval is a conservative Hoeffding bound: estimate ± sqrt(log(40)/2 × sum(block_weight² × (1/n_A + 1/n_B))). It assumes independent encounter outcomes within the fixed design, no repeat shoppers or interference, and is not robust to unmodeled clustering.",
            "Closing locks observations. Do not repeatedly restart pilots or stop based on interim rates; the interval is not valid for optional stopping or selection among many tests.",
            "The sample plan was chosen before collection. Any saved power assessment is conditional on its planning assumptions, not an observed effect. Results apply to the measured product, offer, eligible encounters and staff/shifts; they are not store-wide revenue forecasts.",
        ],
    )
