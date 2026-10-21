"""Scenario scaling preserves the distinction between bounded and unlimited budgets."""
import pytest

from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import Scenario
from store_emulator.engine.scenario import apply_to_personas, compile_scenario


@pytest.mark.parametrize("budget,multiplier,expected", [
    (1, 0.2, 1), (1, 0.5, 1), (2, 0.2, 1), (2, 0.3, 1), (10, 0.2, 2), (10, 1.5, 15), (10, 3, 30),
])
def test_scaled_positive_budget_stays_bounded(budget, multiplier, expected):
    persona = Persona(id="shopper", identity="Shopper", age_group="30s", gender="Female",
                      description="", intent="", purpose="", budget_min=budget, budget_max=budget)
    scenario = Scenario(budget_multiplier=multiplier, traffic_multiplier=2)
    adjusted = apply_to_personas([persona], scenario, compile_scenario(scenario), seed=0)
    assert len(adjusted) == 2
    assert persona.budget_max == budget
    assert all(row.budget_max == expected and 0 <= row.budget_min <= row.budget_max for row in adjusted)


@pytest.mark.parametrize("multiplier", [0.2, 0.5, 1.5, 3])
def test_scaled_unlimited_budget_stays_unlimited(multiplier):
    persona = Persona(id="shopper", identity="Shopper", age_group="30s", gender="Female",
                      description="", intent="", purpose="", budget_min=0, budget_max=0)
    scenario = Scenario(budget_multiplier=multiplier)
    adjusted = apply_to_personas([persona], scenario, compile_scenario(scenario), seed=0)
    assert adjusted[0].budget_max == 0
