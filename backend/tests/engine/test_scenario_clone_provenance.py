"""Extra visits remain copies when optimization chooses distinct customer profiles."""

import math

import pytest

from store_emulator.domain.scenario import Scenario
from store_emulator.engine.optimize.evaluate import select_personas
from store_emulator.engine.scenario import apply_to_personas, compile_scenario
from tests.engine.test_scenario_clone_ids import persona


@pytest.mark.parametrize("multiplier", [1.25, 2, 5])
@pytest.mark.parametrize("seed", [0, 1, 261023])
def test_expanded_traffic_does_not_replace_available_profiles_with_copies(multiplier, seed):
    originals = [persona(f"profile_{i}") for i in range(24)]
    source = originals + [p.model_copy(update={"id": f"daily_{p.id}", "twin_of": p.id}) for p in originals]
    scenario = Scenario(traffic_multiplier=multiplier)
    expanded = apply_to_personas(source, scenario, compile_scenario(scenario), seed=seed)
    panel = select_personas(expanded, len(originals), seed=seed)
    assert {p.id for p in panel} == {p.id for p in originals}
    assert len({p.identity for p in panel}) == len(originals)
    assert all(not p.twin_of for p in originals)


@pytest.mark.parametrize("multiplier", [.4, 1, 1.5, 5])
@pytest.mark.parametrize("scale_traffic", [False, True])
def test_lineage_counts_budgets_and_ids_survive_repeated_traffic_scaling(multiplier, scale_traffic):
    original = persona("customer").model_copy(update={"budget_min": 100, "budget_max": 300})
    twin = original.model_copy(update={"id": "customer~s1", "twin_of": original.id})
    filtered = persona("customer~s2", day=2)
    source = [original, twin, filtered]
    before = [p.model_dump() for p in source]
    scenario = Scenario(only_days=[1], traffic_multiplier=multiplier, budget_multiplier=1.5)
    effects = compile_scenario(scenario)
    first = apply_to_personas(source, scenario, effects, seed=7, scale_traffic=scale_traffic)
    if scale_traffic:
        assert 2 * math.floor(multiplier) <= len(first) <= 2 * math.ceil(multiplier)
    else:
        assert len(first) == 2
    assert len({p.id for p in first}) == len(first)
    assert filtered.id not in {p.id for p in first}
    for p in first:
        assert p.twin_of == ("" if p.id == original.id else original.id)
        assert (p.budget_min, p.budget_max) == (150, 450)
    repeated = apply_to_personas(first, scenario, effects, seed=11, scale_traffic=scale_traffic)
    assert len({p.id for p in repeated}) == len(repeated)
    for p in repeated:
        assert p.twin_of == ("" if p.id == original.id else original.id)
    assert [p.model_dump() for p in source] == before


@pytest.mark.parametrize("size", [1, 8, 20, 21, 60, 100])
def test_panel_can_still_include_copies_when_more_visitors_are_requested(size):
    original = [persona(f"profile_{i}") for i in range(20)]
    scenario = Scenario(traffic_multiplier=5)
    expanded = apply_to_personas(original, scenario, compile_scenario(scenario), seed=261023)
    panel = select_personas(expanded, size, seed=261023)
    assert len(panel) == size
    assert sum(not p.twin_of for p in panel) == min(size, len(original))
    assert len({p.id for p in panel}) == size
    assert [p.id for p in panel] == [p.id for p in expanded if p.id in {q.id for q in panel}]
