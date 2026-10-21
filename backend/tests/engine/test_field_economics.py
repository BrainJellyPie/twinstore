import csv
import io
import math

import pytest
from pydantic import ValidationError

from store_emulator.domain.field_economics import PilotEconomicsRequest
from store_emulator.domain.field_pilot import FieldPilot, PilotRequest
from store_emulator.domain.staff_pitch import PitchProduct, PitchVariant
from store_emulator.engine.marketing.field_economics import economics_csv, pilot_economics
from store_emulator.engine.marketing.field_pilot import allocate_pilot, analyze_pilot


def pilot():
    design = PilotRequest(name="Offline costs", eligibility="One eligible encounter per shopper", outcome_window="This visit",
                          blocks=[{"staff_id": "s1", "shift_id": "am", "encounters": 20},
                                  {"staff_id": "s2", "shift_id": "pm", "encounters": 20}])
    p = FieldPilot(pilot_id="pilot_test", pitch_id="pit_test", created_at="now", updated_at="now", finalized_at="closed",
                   revision=2, design=design, product=PitchProduct(sku="tea", name="Tea", price=2000, currency="KRW"),
                   variants=(PitchVariant(name="A", script="Hello"), PitchVariant(name="B", script="Can I help?")),
                   context="Tea shelf", product_facts="", assignments=allocate_pilot("pilot_test", design))
    seen = {"A": 0, "B": 0}
    for row in p.assignments:
        seen[row.arm] += 1
        row.enrolled = True; row.delivered = False; row.purchased = seen[row.arm] <= (4 if row.arm == "A" else 10)
    return p


def request(**changes):
    return PilotEconomicsRequest.model_validate({"revision": 2, "currency": "KRW", "contribution_per_conversion_minor": 1000,
        "labor_per_hour_minor": 36000, "seconds_per_encounter_a": 30, "seconds_per_encounter_b": 60,
        "eligible_encounters_per_day": 100, **changes})


def test_costs_transform_original_interval_and_keep_exact_break_even_zero():
    p = pilot(); before = p.model_dump(); source = analyze_pilot(p)
    result = pilot_economics(p, request())
    assert result.conversion_difference == pytest.approx(source.difference) == 0.3
    assert result.incremental_labor_minor == 300 and result.break_even_difference == 0.3
    assert result.per_encounter.estimate_minor == 0 and result.per_day.estimate_minor == 0
    assert result.per_encounter.low_minor == source.ci_low * 1000 - 300
    assert result.per_encounter.high_minor == source.ci_high * 1000 - 300
    assert result.per_encounter.low_minor < 0 < result.per_encounter.high_minor
    assert result.per_day.low_minor == result.per_encounter.low_minor * 100
    assert result.per_day.high_minor == result.per_encounter.high_minor * 100
    assert p.model_dump() == before
    for row in p.assignments:
        row.delivered = True
    p.product.price = 999999
    assert pilot_economics(p, request()) == result


def test_cheaper_b_and_fractional_minor_units_do_not_get_clipped_or_rounded():
    result = pilot_economics(pilot(), request(seconds_per_encounter_a=1, seconds_per_encounter_b=0, labor_per_hour_minor=1))
    assert result.incremental_labor_minor == pytest.approx(-1 / 3600)
    assert result.break_even_difference == pytest.approx(-1 / 3600000)
    assert result.per_encounter.estimate_minor == pytest.approx(300 + 1 / 3600)
    result = pilot_economics(pilot(), request(contribution_per_conversion_minor=1, labor_per_hour_minor=1000000,
                                             seconds_per_encounter_a=0, seconds_per_encounter_b=3600))
    assert result.break_even_difference == 1000000 and result.per_encounter.high_minor < 0


def test_zero_contribution_zero_cost_and_zero_daily_traffic_have_distinct_meanings():
    result = pilot_economics(pilot(), request(contribution_per_conversion_minor=0))
    assert result.break_even_difference is None
    assert result.per_encounter.estimate_minor == result.per_encounter.low_minor == result.per_encounter.high_minor == -300
    free = pilot_economics(pilot(), request(labor_per_hour_minor=0, eligible_encounters_per_day=0))
    assert free.incremental_labor_minor == free.break_even_difference == 0
    assert free.per_encounter.estimate_minor == 300
    assert free.per_day.estimate_minor == free.per_day.low_minor == free.per_day.high_minor == 0


@pytest.mark.parametrize("outcome", [False, True])
def test_all_zero_or_one_purchases_retain_conversion_uncertainty(outcome):
    p = pilot()
    for row in p.assignments:
        row.purchased = outcome
    result = pilot_economics(p, request(labor_per_hour_minor=0))
    assert result.conversion_difference == result.per_encounter.estimate_minor == 0
    assert result.per_encounter.low_minor < 0 < result.per_encounter.high_minor


def test_complementing_outcomes_and_swapping_times_reverses_the_cost_scenario():
    p = pilot(); original = pilot_economics(p, request(seconds_per_encounter_b=40))
    for row in p.assignments:
        row.purchased = not row.purchased
    reversed_result = pilot_economics(p, request(seconds_per_encounter_a=40, seconds_per_encounter_b=30))
    assert reversed_result.per_encounter.estimate_minor == -original.per_encounter.estimate_minor
    assert reversed_result.per_encounter.low_minor == pytest.approx(-original.per_encounter.high_minor)
    assert reversed_result.per_encounter.high_minor == pytest.approx(-original.per_encounter.low_minor)


@pytest.mark.parametrize("changes", [
    {"labor_per_hour_minor": True}, {"contribution_per_conversion_minor": -1}, {"seconds_per_encounter_a": 1.5},
    {"seconds_per_encounter_b": "2"}, {"eligible_encounters_per_day": 1000001}, {"revision": -1},
    {"labor_per_hour_minor": 1000000001}, {"seconds_per_encounter_b": 3601}, {"contribution_per_conversion_minor": float("inf")},
])
def test_invalid_assumptions_are_not_coerced(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_maximum_inputs_remain_finite_and_unmodified():
    inputs = request(contribution_per_conversion_minor=1000000000, labor_per_hour_minor=1000000000,
                     seconds_per_encounter_a=0, seconds_per_encounter_b=3600, eligible_encounters_per_day=1000000)
    result = pilot_economics(pilot(), inputs)
    assert result.assumptions == inputs
    assert all(math.isfinite(value) and abs(value) <= 2e15 for value in result.per_day.model_dump().values())


@pytest.mark.parametrize("mutate", [
    lambda p: setattr(p, "finalized_at", ""), lambda p: p.assignments.pop(),
    lambda p: setattr(p.assignments[0], "enrolled", False), lambda p: setattr(p.assignments[0], "purchased", None),
    lambda p: setattr(p.assignments[0], "delivered", None), lambda p: setattr(p.assignments[0], "staff_id", "other"),
])
def test_open_missing_or_mismatched_records_cannot_be_used_for_cost_scenarios(mutate):
    p = pilot(); mutate(p)
    with pytest.raises(ValueError):
        pilot_economics(p, request())


@pytest.mark.parametrize("changes", [{"revision": 1}, {"currency": "USD"}])
def test_stale_revision_and_currency_conversion_are_rejected(changes):
    with pytest.raises(ValueError):
        pilot_economics(pilot(), request(**changes))


def test_csv_retains_assumptions_snapshot_units_and_undefined_threshold():
    p = pilot(); p.product.sku = "=SKU"
    report = pilot_economics(p, request(contribution_per_conversion_minor=0))
    rows = list(csv.DictReader(io.StringIO(economics_csv(report))))
    assert len(rows) == 1 and rows[0]["revision"] == "2" and rows[0]["target_sku"] == "'=SKU"
    assert rows[0]["break_even_difference"] == "" and rows[0]["difference_unit"] == "proportion"
    assert rows[0]["contribution_per_conversion_minor"] == "0" and rows[0]["seconds_per_encounter_a"] == "30"
    assert rows[0]["per_day_estimate_minor"] == "-30000.0"
    assert "not realized profit" in rows[0]["interpretation"]


def test_zero_traffic_has_no_negative_zero_in_exported_costs():
    report = pilot_economics(pilot(), request(eligible_encounters_per_day=0, seconds_per_encounter_b=3600))
    assert all(math.copysign(1, v) == 1 for v in report.per_day.model_dump().values())
    exported = next(csv.DictReader(io.StringIO(economics_csv(report))))
    assert all(exported[k] == "0.0" for k in ("per_day_estimate_minor", "per_day_low_minor", "per_day_high_minor"))


def test_zero_margin_and_equal_time_have_no_signed_zero_range():
    report = pilot_economics(pilot(), request(contribution_per_conversion_minor=0, seconds_per_encounter_a=60))
    assert all(v == 0 and math.copysign(1, v) == 1 for v in report.per_encounter.model_dump().values())
