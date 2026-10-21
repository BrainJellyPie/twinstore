"""Signed seeds accepted by simulation requests must also work during final analysis."""

import pytest

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.marketing import ShelfChoice
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.marketing.experiment import focus_outcomes, segment_lifts
from store_emulator.engine.marketing.shelf_test import compare_shelves


@pytest.mark.parametrize("operation", ["runs", "focus", "segments", "shelves"])
@pytest.mark.parametrize("seed", [-1, -(2**63), 0, 7])
def test_signed_seeds_produce_reproducible_bootstrap_results(operation, seed):
    control: list[CustomerResult] = []
    variant: list[CustomerResult] = []
    for i in range(20):
        for outcomes, extra in ((control, 0), (variant, i % 5)):
            price = 100 + i + extra
            outcomes.append(CustomerResult(
                persona_id=f"p{i}", day=Weekday.MON, arrival_time="12:00:00", total_spent=price,
                timeline=[TimelineEvent(elapsed_sec=1, x=1, y=1, action=Action.BUY,
                                        target_rack="shelf", product_sku="tea", product_name="Tea", price=price)],
            ))
    panel = [Persona(id=f"p{i}", identity="Shopper", age_group="20s", gender="Female",
                     description="Tea", intent="tea", purpose="tea") for i in range(20)]
    if operation == "runs":
        call = lambda: compare_runs(control, variant, n_bootstrap=200, seed=seed)
    elif operation == "focus":
        call = lambda: focus_outcomes(control, variant, ["tea"], {"tea": "Tea"}, n_bootstrap=200, seed=seed)
    elif operation == "segments":
        call = lambda: segment_lifts(control, variant, panel, ["tea"], n_bootstrap=200, seed=seed)
    else:
        choices: list[ShelfChoice] = []
        for i in range(20):
            choices.extend([
                ShelfChoice(respondent=f"p{i}", age_group="20s", gender="Female", arm="control",
                            pick_sku="tea" if i % 2 else "", noticed=["tea"] if i % 2 else []),
                ShelfChoice(respondent=f"p{i}", age_group="20s", gender="Female", arm="test",
                            pick_sku="tea" if i % 3 else "", noticed=["tea"] if i % 3 else []),
            ])
        call = lambda: compare_shelves(choices, "tea", n_bootstrap=200, seed=seed)
    result = call()
    assert result
    assert result == call()
