import pytest

from store_emulator.domain.factorial import FactorialRequest, PairedSnapshot
from store_emulator.engine.marketing.factorial import analyze_factorial, factorial_csv


def snapshot(n=40):
    price = {"kind": "price", "sku": "tea", "price": 100}
    sign = {"kind": "promo", "sku": "tea", "promo": "SALE"}
    variants = [{"name": "Price", "changes": [price]}, {"name": "Sign", "changes": [sign]},
                {"name": "Both", "changes": [price, sign]}]
    ids = [f"p_{i:04}" for i in range(n)]
    return PairedSnapshot.model_validate({"experiment_id": "exp_test", "currency": "USD",
        "request": {"setup_id": "setup_test", "panel": max(20, n), "variants": variants}, "panel_ids": ids,
        "arms": [{"name": name, "store_sha256": str(index) * 64,
            "outcomes": [{"persona_id": pid, "spend": i * 1000 + effect, "units": 1, "bought": True}
                for i, pid in enumerate(ids)]}
            for index, (name, effect) in enumerate(zip(["Control", "Price", "Sign", "Both"], [0, 2, 3, 12], strict=True))]})


def request(**changes):
    return FactorialRequest.model_validate({"source_sha256": "a" * 64, "price_arm": "Price", "sign_arm": "Sign",
        "combined_arm": "Both", "metric": "spend", **changes})


def test_hand_calculated_main_effects_and_difference_in_differences_are_paired():
    result = analyze_factorial(snapshot(), request())
    assert result.complete_panel == result.sampled_panel == 40 and result.intervals_available
    assert [c.estimate for c in result.contrasts] == [5.5, 6.5, 7]
    # Large respondent baseline differences cancel; independent-cell resampling would not give point intervals.
    assert [(c.ci_low, c.ci_high) for c in result.contrasts] == [(5.5, 5.5), (6.5, 6.5), (7, 7)]
    assert [c.mean for c in result.cells] == [19500, 19502, 19503, 19512]
    assert "11-10-01+00" in factorial_csv(result)


def test_mixed_manipulations_cannot_be_presented_as_a_factorial_interaction():
    data = snapshot().model_dump(mode="json")
    data["request"]["variants"][2]["changes"][0]["price"] = 90
    source = PairedSnapshot.model_validate(data)
    with pytest.raises(ValueError, match="exactly the same two"):
        analyze_factorial(source, request())


@pytest.mark.parametrize("n", [1, 29, 30])
def test_minimum_panel_and_interval_threshold(n):
    result = analyze_factorial(snapshot(n), request())
    assert result.complete_panel == n and result.intervals_available == (n >= 30)
    assert [c.estimate for c in result.contrasts] == [5.5, 6.5, 7]
    assert all((c.ci_low is not None) == (n >= 30) for c in result.contrasts)


def test_missing_cells_use_one_common_cohort_and_never_impute_zero():
    data = snapshot().model_dump(mode="json")
    data["arms"][1]["outcomes"].pop(0)
    data["arms"][2]["outcomes"].pop(1)
    result = analyze_factorial(PairedSnapshot.model_validate(data), request())
    assert result.complete_panel == 38 and not result.intervals_available
    assert [c.available for c in result.cells] == [40, 39, 39, 40]
    assert [c.mean for c in result.cells] == [20500, 20502, 20503, 20512]
    assert result.rows[0].values == [0, None, 3, 12] and not result.rows[0].complete
    assert result.rows[1].values[2] is None and not result.rows[1].complete
    assert all(c.ci_low is c.ci_high is None for c in result.contrasts)
    assert "p_0000,False,0.0,,3.0,12.0" in factorial_csv(result)


def test_empty_intersection_and_completely_missing_shopper_have_no_fabricated_estimates():
    data = snapshot().model_dump(mode="json")
    for arm in data["arms"]:
        arm["outcomes"].pop()
    data["arms"][3]["outcomes"] = []
    result = analyze_factorial(PairedSnapshot.model_validate(data), request())
    assert result.sampled_panel == 40 and result.complete_panel == 0
    assert all(c.mean is None for c in result.cells)
    assert all(c.estimate is c.ci_low is c.ci_high is None for c in result.contrasts)
    assert result.rows[-1].values == [None] * 4
    assert 'NaN' not in result.model_dump_json()


def test_order_independence_and_exact_negative_zero_and_large_values():
    data = snapshot().model_dump(mode="json")
    for i, arm in enumerate(data["arms"]):
        for r in arm["outcomes"]:
            r["spend"] = 1_000_000_000_000 - i
    a = analyze_factorial(PairedSnapshot.model_validate(data), request())
    data["panel_ids"].reverse()
    for arm in data["arms"]: arm["outcomes"].reverse()
    b = analyze_factorial(PairedSnapshot.model_validate(data), request())
    assert a == b and [c.estimate for c in a.contrasts] == [-1, -2, 0]
    assert all(c.ci_low == c.ci_high == c.estimate for c in a.contrasts)
    assert "-0.0" not in factorial_csv(a)


def test_binary_purchase_and_unit_outcomes_are_distinct_from_spend():
    data = snapshot().model_dump(mode="json")
    for i, arm in enumerate(data["arms"]):
        for r in arm["outcomes"]:
            r.update(spend=0, units=int(i == 3), bought=i == 3)
    source = PairedSnapshot.model_validate(data)
    assert [c.estimate for c in analyze_factorial(source, request()).contrasts] == [0, 0, 0]
    for metric in ["units", "bought"]:
        assert [c.estimate for c in analyze_factorial(source, request(metric=metric)).contrasts] == [.5, .5, 1]


@pytest.mark.parametrize("field,value", [("spend", -1), ("spend", 1_000_000_000_001), ("spend", 0.5),
    ("spend", float("inf")), ("spend", float("nan")), ("spend", True), ("spend", "0"),
    ("units", -1), ("units", 1_000_000_001), ("bought", 1), ("bought", "false"), ("persona_id", ""),
    ("persona_id", "x\n"), ("persona_id", "茶")])
def test_corrupt_outcome_types_and_limits_reject_the_snapshot(field, value):
    data = snapshot().model_dump(mode="json")
    data["arms"][0]["outcomes"][0][field] = value
    with pytest.raises(ValueError): PairedSnapshot.model_validate(data)


@pytest.mark.parametrize("mutation", ["duplicate_panel", "duplicate_outcome", "foreign", "wrong_order", "empty_panel", "too_many_sampled"])
def test_identity_and_cardinality_integrity(mutation):
    data = snapshot().model_dump(mode="json")
    match mutation:
        case "duplicate_panel": data["panel_ids"].append(data["panel_ids"][0])
        case "duplicate_outcome": data["arms"][0]["outcomes"].append(data["arms"][0]["outcomes"][0])
        case "foreign": data["arms"][0]["outcomes"][0]["persona_id"] = "other"
        case "wrong_order": data["arms"].reverse()
        case "empty_panel": data["panel_ids"] = []
        case "too_many_sampled": data["request"]["panel"] = 20
    with pytest.raises(ValueError): PairedSnapshot.model_validate(data)


@pytest.mark.parametrize("mutation", ["noop", "warning", "other_sku", "extra_change", "wrong_kind", "missing_arm"])
def test_unsupported_designs_are_rejected(mutation):
    data = snapshot().model_dump(mode="json"); req = request()
    match mutation:
        case "noop": data["arms"][1]["store_sha256"] = data["arms"][0]["store_sha256"]
        case "warning": data["arms"][2]["warnings"] = ["Unapplied sign"]
        case "other_sku": data["request"]["variants"][1]["changes"][0]["sku"] = "other"
        case "extra_change": data["request"]["variants"][2]["changes"].append({"kind": "promo", "sku": "tea", "promo": "OTHER"})
        case "wrong_kind": data["request"]["variants"][0]["changes"][0]["kind"] = "package"
        case "missing_arm": req = request(price_arm="Missing")
    with pytest.raises(ValueError): analyze_factorial(PairedSnapshot.model_validate(data), req)


def test_reversed_combination_order_unicode_and_formula_prefix_labels_export_safely():
    data = snapshot().model_dump(mode="json")
    data["request"]["variants"][2]["changes"].reverse()
    names = ["=Price", "표지,茶", "@Both"]
    for i, name in enumerate(names):
        data["request"]["variants"][i]["name"] = name
        data["arms"][i + 1]["name"] = name
    result = analyze_factorial(PairedSnapshot.model_validate(data), request(price_arm=names[0], sign_arm=names[1], combined_arm=names[2]))
    assert [c.estimate for c in result.contrasts] == [5.5, 6.5, 7]
    csv = factorial_csv(result)
    assert "'=Price" in csv and "'@Both" in csv and '"표지,茶"' in csv


def test_full_three_thousand_panel_is_bounded_and_an_extra_sample_is_rejected():
    data = snapshot(3000)
    result = analyze_factorial(data, request())
    assert result.complete_panel == 3000 and result.intervals_available
    assert [c.estimate for c in result.contrasts] == [5.5, 6.5, 7]
    invalid = data.model_dump(mode="json"); invalid["panel_ids"].append("extra")
    with pytest.raises(ValueError): PairedSnapshot.model_validate(invalid)


@pytest.mark.parametrize("changes", [{"metric": "profit"}, {"metric": ""}, {"source_sha256": ""},
    {"source_sha256": "g" * 64}, {"price_arm": ""}, {"price_arm": "Control"}, {"price_arm": "Sign"},
    {"combined_arm": "x" * 41}])
def test_invalid_analysis_request(changes):
    with pytest.raises(ValueError): request(**changes)


@pytest.mark.parametrize("spend,units,bought", [(100, 0, False), (0, 1, False), (100, 1, False), (0, 0, True), (100, 0, True)])
def test_inconsistent_purchase_records_are_not_accepted_as_valid_paired_evidence(spend, units, bought):
    data = snapshot().model_dump(mode="json")
    data["arms"][0]["outcomes"][0].update(spend=spend, units=units, bought=bought)
    with pytest.raises(ValueError, match="purchase"):
        PairedSnapshot.model_validate(data)


def test_capture_keeps_zero_price_purchases_without_persona_narratives():
    from store_emulator.domain.customer import CustomerResult, TimelineEvent
    from store_emulator.domain.store import Store
    from store_emulator.domain.types import Action, Weekday
    from store_emulator.engine.marketing.factorial import capture_paired_outcomes
    req = snapshot(1).request
    store = Store(id="store", name="Fixture", type="convenience", grid_size=(1, 1))
    result = CustomerResult(persona_id="p_0000", day=Weekday.MON, arrival_time="12:00", total_spent=0,
        timeline=[TimelineEvent(elapsed_sec=1, x=0, y=0, action=Action.BUY, price=0, product_sku="tea")])
    source = capture_paired_outcomes("exp_test", "USD", req, ["p_0000"],
        [(name, store, []) for name in ["Control", "Price", "Sign", "Both"]], [[result]] * 4)
    assert all(a.outcomes[0].bought and a.outcomes[0].units == 1 and a.outcomes[0].spend == 0 for a in source.arms)
    assert "timeline" not in source.model_dump_json() and "arrival_time" not in source.model_dump_json()
