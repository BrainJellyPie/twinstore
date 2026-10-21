"""Conservative power bounds for the field pilot's existing 95% Hoeffding interval."""

import math

from store_emulator.domain.field_planning import PilotPlanningRequest, PilotPlanningResult


def plan_pilot(request: PilotPlanningRequest) -> PilotPlanningResult:
    a = request.assumptions
    total = sum(request.block_counts)
    count = len(request.block_counts)
    # Balanced A/B in each block and planned-count weights give sum(weights²) = 4/N.
    # Under an absolute true effect d > r, P(failing to exclude zero in that direction)
    # <= exp(-N*(d-r)²/2), where r = sqrt(2*log(40)/N).
    radius = math.sqrt(2 * math.log(40) / total)
    # A finite sample never implies certainty, even when exp underflows in floating point.
    power = min(math.nextafter(1.0, 0.0), -math.expm1(-total * max(0.0, a.minimum_effect - radius) ** 2 / 2))
    required = max(40, 4 * count, 2 * math.ceil(
        (math.sqrt(math.log(40)) + math.sqrt(-math.log1p(-a.target_power))) ** 2 / a.minimum_effect ** 2))
    suggestion: list[int] | None = None
    if required <= min(10_000, 2000 * count):
        pairs, extra = divmod(required // 2, count)
        suggestion = [2 * (pairs + (i < extra)) for i in range(count)]
    return PilotPlanningResult(
        assumptions=a, block_counts=request.block_counts, planned_encounters=total,
        required_encounters=required, planned_power_lower_bound=power, planned_ci_half_width=radius,
        planned_days=math.ceil(total / a.eligible_per_day), required_days=math.ceil(required / a.eligible_per_day),
        suggested_block_counts=suggestion,
        notes=[
            "Planning assumptions only, not observed conversion or a forecast of sales. No synthetic panel score or baseline conversion is used.",
            "Minimum effect is an absolute percentage-point difference, in either direction, for the planned staff/shift mix. The power number is a conservative lower bound, not an estimate of actual power; a zero bound does not mean detection is impossible.",
            "For balanced blocks weighted by planned counts, the unclipped 95% interval half-width is r = sqrt(2*log(40)/N). Power is bounded below by 1-exp(-N*max(0, effect-r)^2/2). Required N is rounded up to an even total and respects the minimum block size.",
            "The bound assumes independent encounter outcomes, each customer used once, complete enrollment and outcomes for every planned slot, no interference or unmodeled clustering, and one fixed-sample comparison. Blocking does not correct dependence between customers in the same shift.",
            "Choose the effect, sample size and stopping rule before collection. Do not use interim results to resize, restart, or select among repeated tests. Missing outcomes or an early close prevent confirmatory inference.",
            "Daily capacity is your estimate of unique eligible encounters across all participating staff/shifts, not total footfall. Days are rounded up and exclude waiting for the saved outcome window; calendar availability and each block's capacity need a separate operational check.",
            "An even allocation suggestion redistributes counts across the existing blocks and therefore changes their analysis weights. Review the staff/shift mix before saving. Recommendations above capacity are shown without silently capping the required sample.",
        ],
    )
