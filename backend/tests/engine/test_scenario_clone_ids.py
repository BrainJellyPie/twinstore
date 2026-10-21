"""Traffic expansion preserves each original shopper's identity and unique clone IDs."""
import pytest

from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import Scenario
from store_emulator.engine.scenario import apply_to_personas, compile_scenario


def persona(identifier, day=1):
    return Persona(id=identifier, day=day, identity=f"Shopper {identifier}", age_group="20s",
                   gender="Female", description="", intent="snack", purpose="snack")


@pytest.mark.parametrize("identifiers", [
    ["customer", "customer~s1", "customer~s2"],
    ["customer", "customer~s1", "customer~s1~s1"],
    ["a~s0", "a~s0~s1", "a~s0~s2"],
    ["customer", "other"],
])
@pytest.mark.parametrize("multiplier", [1, 1.5, 2, 5])
def test_expansion_preserves_originals_and_unique_reproducible_ids(identifiers, multiplier):
    source = [persona(identifier) for identifier in identifiers]
    scenario = Scenario(traffic_multiplier=multiplier)
    effects = compile_scenario(scenario)
    first = apply_to_personas(source, scenario, effects, seed=7)
    ids = [p.id for p in first]
    assert len(ids) == len(set(ids))
    assert set(identifiers) <= set(ids)
    assert [p.id for p in source] == identifiers
    assert first == apply_to_personas(source, scenario, effects, seed=7)
    reordered = apply_to_personas(list(reversed(source)), scenario, effects, seed=7)
    assert {p.id: p for p in first} == {p.id: p for p in reordered}


def test_clones_do_not_take_ids_of_filtered_original_shoppers():
    source = [persona("customer"), persona("customer~s1", day=2)]
    scenario = Scenario(only_days=[1], traffic_multiplier=2)
    result = apply_to_personas(source, scenario, compile_scenario(scenario), seed=0)
    assert [p.id for p in result] == ["customer", "customer~s2"]


def test_ordinary_clone_ids_remain_backwards_compatible():
    scenario = Scenario(traffic_multiplier=3)
    result = apply_to_personas([persona("customer")], scenario, compile_scenario(scenario), seed=0)
    assert [p.id for p in result] == ["customer", "customer~s1", "customer~s2"]
