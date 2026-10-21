"""Leave one staff, shift or block out; no refitting, inference or outcome selection."""

import csv
import io
from fractions import Fraction

from store_emulator.domain.field_pilot import FieldPilot, PilotAssignment
from store_emulator.domain.field_sensitivity import (
    GroupDeletion, PilotSensitivityReport, SensitivityScope, SensitivitySummary,
)
from store_emulator.engine.marketing.field_pilot import allocate_pilot


def analyze_sensitivity(pilot: FieldPilot) -> PilotSensitivityReport:
    if not pilot.finalized_at:
        raise ValueError("Close and lock the completed fixed pilot before requesting sensitivity checks")
    expected = allocate_pilot(pilot.pilot_id, pilot.design)
    def identity(row: PilotAssignment) -> tuple[str, str, str, int, str]:
        return row.assignment_id, row.staff_id, row.shift_id, row.sequence, row.arm

    if sorted(map(identity, pilot.assignments)) != sorted(map(identity, expected)):
        raise ValueError("Saved assignments do not match the fixed pilot design")
    if any(r.enrolled is not True or r.delivered is None or r.purchased is None for r in pilot.assignments):
        raise ValueError("Sensitivity checks require every planned encounter and all purchase and delivery outcomes; no rows are dropped or imputed")

    sizes = {(b.staff_id, b.shift_id): b.encounters for b in pilot.design.blocks}
    purchases = {key: {"A": 0, "B": 0} for key in sizes}
    for row in pilot.assignments:
        purchases[(row.staff_id, row.shift_id)][row.arm] += int(row.purchased is True)
    differences = {key: Fraction(counts["B"] - counts["A"], sizes[key] // 2) for key, counts in purchases.items()}
    total = sum(sizes.values())
    full = sum((differences[key] * size for key, size in sizes.items()), Fraction()) / total
    groups: list[GroupDeletion] = []
    summaries: list[SensitivitySummary] = []
    scopes: tuple[SensitivityScope, ...] = ("staff", "shift", "block")
    for scope in scopes:
        partitions: dict[tuple[str, str], set[tuple[str, str]]] = {}
        for staff, shift in sizes:
            group = (staff if scope != "shift" else "", shift if scope != "staff" else "")
            partitions.setdefault(group, set()).add((staff, shift))
        scoped: list[GroupDeletion] = []
        for (staff, shift), removed in sorted(partitions.items()):
            removed_count = sum(sizes[key] for key in removed)
            remaining = total - removed_count
            estimate = sum((differences[key] * size for key, size in sizes.items() if key not in removed), Fraction()) / remaining if remaining else None
            scoped.append(GroupDeletion(
                scope=scope, staff_id=staff, shift_id=shift, removed_blocks=len(removed),
                removed_encounters=removed_count, removed_weight=removed_count / total, remaining_encounters=remaining,
                difference=float(estimate) if estimate is not None else None,
                change=float(estimate - full) if estimate is not None else None,
                opposite_sign=estimate * full < 0 if estimate is not None else None,
            ))
        estimates = [row.difference for row in scoped if row.difference is not None]
        changes = [abs(row.change) for row in scoped if row.change is not None]
        summaries.append(SensitivitySummary(
            scope=scope, groups=len(scoped), estimable=len(estimates),
            minimum=min(estimates) if estimates else None, maximum=max(estimates) if estimates else None,
            max_absolute_change=max(changes) if changes else None,
            opposite_sign_count=sum(row.opposite_sign is True for row in scoped),
        ))
        groups.extend(scoped)
    return PilotSensitivityReport(
        pilot_id=pilot.pilot_id, revision=pilot.revision, finalized_at=pilot.finalized_at,
        target_sku=pilot.product.sku, planned_encounters=total, blocks=len(sizes), difference=float(full),
        groups=groups, summaries=summaries, notes=[
            "Descriptive sensitivity checks of this locked, fully completed fixed plan only. No p-values, new confidence intervals, winners or sales forecasts are produced. The original full-plan estimate remains the primary result.",
            "For each deletion, remove all blocks for one staff alias, one shift ID, or one staff/shift pair. Reweight remaining blocks by their original planned encounter counts divided by the remaining planned total. All assigned encounters remain included regardless of script delivery or refusal (intention to treat).",
            "Shift IDs are matched exactly across staff aliases. Use distinct IDs for distinct shifts; reused aliases or IDs can merge unrelated people or shifts. This report cannot verify identities or correct those records.",
            "An opposite sign means a strictly positive full-plan estimate becomes negative, or vice versa. Zero is not an opposite sign. A range summarizes deletion estimates; it is not a confidence interval. Removing the only group leaves no comparison, not a zero effect.",
            "All groups are reported in stable identifier order. Do not select a favorable deletion, change the primary estimate, restart pilots or use these comparisons as repeated hypothesis tests. Group-deletion rows overlap and are not independent replications.",
            "A large change can reflect sampling noise, group composition, effect heterogeneity or protocol differences. It does not establish a staff performance effect or identify confounding. Stable signs do not prove robustness or causality; this procedure does not fix clustering, repeated shoppers, interference or unmeasured confounding.",
            "Open, incomplete, unused-slot or mismatched-assignment pilots are rejected; no complete-case subset or missing-outcome imputation is used. These checks do not verify that the saved outcome window or collection protocol was followed.",
        ],
    )


def sensitivity_csv(report: PilotSensitivityReport) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["method", "interpretation", "difference_unit", "pilot_id", "revision", "finalized_at", "target_sku", "planned_encounters",
                     "full_difference", "scope", "excluded_staff_id", "excluded_shift_id", "removed_blocks",
                     "removed_encounters", "removed_weight", "remaining_encounters", "difference", "change", "opposite_sign"])
    for group in report.groups:
        row: list[str | int | float | None] = [report.method, "Descriptive sensitivity only; retain the full-plan primary result.",
            "proportion", report.pilot_id, report.revision, report.finalized_at,
            report.target_sku, report.planned_encounters, report.difference, group.scope, group.staff_id, group.shift_id,
            group.removed_blocks, group.removed_encounters, group.removed_weight, group.remaining_encounters,
            group.difference, group.change, int(group.opposite_sign) if group.opposite_sign is not None else None]
        writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
    return out.getvalue()
