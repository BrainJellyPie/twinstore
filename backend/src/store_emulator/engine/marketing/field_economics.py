"""Conditional contribution scenarios, never realized profit or daily sales forecasts."""

import csv
import io
from fractions import Fraction

from store_emulator.domain.field_economics import ConditionalContribution, PilotEconomicsReport, PilotEconomicsRequest
from store_emulator.domain.field_pilot import FieldPilot, PilotAssignment
from store_emulator.engine.marketing.field_pilot import allocate_pilot, analyze_pilot


def pilot_economics(pilot: FieldPilot, request: PilotEconomicsRequest) -> PilotEconomicsReport:
    if request.revision != pilot.revision:
        raise ValueError("The saved pilot revision changed; reload the pilot before calculating costs")
    if request.currency != pilot.product.currency:
        raise ValueError("Use the saved product currency; no currency conversion is performed")
    if not pilot.finalized_at:
        raise ValueError("Close the completed fixed pilot before calculating a cost scenario")

    def identity(row: PilotAssignment) -> tuple[str, str, str, int, str]:
        return row.assignment_id, row.staff_id, row.shift_id, row.sequence, row.arm

    if sorted(map(identity, pilot.assignments)) != sorted(map(identity, allocate_pilot(pilot.pilot_id, pilot.design))):
        raise ValueError("Saved assignments do not match the fixed pilot design")
    if any(r.enrolled is not True or r.delivered is None or r.purchased is None for r in pilot.assignments):
        raise ValueError("Cost scenarios require every planned encounter and all purchase and delivery outcomes; missing records are not dropped or imputed")
    analysis = analyze_pilot(pilot)
    if analysis.difference is None or analysis.ci_low is None or analysis.ci_high is None:
        raise ValueError("A completed fixed-sample conversion interval is required")
    labor = Fraction((request.seconds_per_encounter_b - request.seconds_per_encounter_a) * request.labor_per_hour_minor, 3600)
    margin = request.contribution_per_conversion_minor
    # Complete balanced blocks with planned-count weights equal pooled arm rates.
    effect = Fraction(sum((1 if row.arm == "B" else -1) for row in pilot.assignments if row.purchased), len(pilot.assignments) // 2)
    per_encounter = ConditionalContribution(
        estimate_minor=float(effect * margin - labor),
        low_minor=analysis.ci_low * margin - float(labor),
        high_minor=analysis.ci_high * margin - float(labor),
    )
    daily = request.eligible_encounters_per_day
    return PilotEconomicsReport(
        pilot_id=pilot.pilot_id, finalized_at=pilot.finalized_at, target_sku=pilot.product.sku,
        planned_encounters=len(pilot.assignments), assumptions=request,
        conversion_difference=float(effect), conversion_ci_low=analysis.ci_low, conversion_ci_high=analysis.ci_high,
        incremental_labor_minor=float(labor), break_even_difference=float(labor / margin) if margin else None,
        per_encounter=per_encounter, per_day=ConditionalContribution(
            estimate_minor=per_encounter.estimate_minor * daily, low_minor=per_encounter.low_minor * daily,
            high_minor=per_encounter.high_minor * daily),
        notes=[
            "This is a conditional cost scenario for switching A to B, not realized profit or a sales forecast. Contribution, labor cost, time and daily traffic are operator assumptions, not measured by this module or inferred from virtual shoppers.",
            "Contribution per converted encounter is the common net target-product contribution for a buyer under either arm, after product costs, discounts and returns but before the staff time entered here. It is not selling price or unit margin unless one unit per buyer is justified. Other basket effects and fixed implementation costs are excluded.",
            "Use average staff seconds per assigned eligible encounter for each arm, including refusals and non-delivery. These are whole-second assumptions for the same population, not time only among buyers or delivered scripts. Use loaded hourly labor cost and avoid counting it twice in contribution.",
            "Incremental labor per encounter = (seconds_B - seconds_A) × hourly cost / 3600. Incremental contribution = (B-minus-A conversion difference × contribution per conversion) - incremental labor. Break-even difference = incremental labor / contribution, without clipping; at zero contribution it is undefined and only assumed labor cost remains.",
            "The conditional range linearly transforms the original conservative fixed-sample 95% conversion interval, holding all cost assumptions fixed. It excludes uncertainty in margins, time, labor and traffic; it is not a new independent test. Editing assumptions does not create new evidence or justify selecting a favorable scenario.",
            "Daily values multiply the same per-encounter scenario by assumed eligible daily encounters. They are not prediction intervals for realized daily profit, do not establish staff capacity or demand, and require the same product, offer, staff/shift mix and eligibility as the pilot.",
            "Every assigned encounter remains in its original arm regardless of script delivery. The calculation does not repair clustering, repeated shoppers, optional stopping, missing records or confounding. Keep the full-plan result and original stopping rule; no observations or saved design are changed.",
            "Money uses currency minor units; calculated expectations can be fractional minor units. No currency conversion is performed. Scenarios are not saved in the project; retain the CSV with its assumptions and source revision.",
        ],
    )


def economics_csv(report: PilotEconomicsReport) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["method", "interpretation", "pilot_id", "revision", "finalized_at", "target_sku", "currency",
                     "planned_encounters", "contribution_per_conversion_minor", "labor_per_hour_minor",
                     "seconds_per_encounter_a", "seconds_per_encounter_b", "eligible_encounters_per_day",
                     "conversion_difference", "conversion_ci_low", "conversion_ci_high", "difference_unit",
                     "incremental_labor_minor", "break_even_difference", "per_encounter_estimate_minor",
                     "per_encounter_low_minor", "per_encounter_high_minor", "per_day_estimate_minor", "per_day_low_minor", "per_day_high_minor"])
    req = report.assumptions
    row: list[str | int | float | None] = [report.method, "Conditional on fixed operator cost and traffic assumptions; not realized profit or a daily prediction interval.",
        report.pilot_id, req.revision, report.finalized_at, report.target_sku, req.currency, report.planned_encounters,
        req.contribution_per_conversion_minor, req.labor_per_hour_minor, req.seconds_per_encounter_a,
        req.seconds_per_encounter_b, req.eligible_encounters_per_day, report.conversion_difference,
        report.conversion_ci_low, report.conversion_ci_high, "proportion", report.incremental_labor_minor,
        report.break_even_difference, report.per_encounter.estimate_minor, report.per_encounter.low_minor,
        report.per_encounter.high_minor, report.per_day.estimate_minor, report.per_day.low_minor, report.per_day.high_minor]
    writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
    return out.getvalue()
