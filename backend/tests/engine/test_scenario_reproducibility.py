import json
import os
import subprocess
import sys

import pytest

from store_emulator.domain.scenario import Scenario, ScenarioPriors
from store_emulator.engine.scenario import compile_scenario


@pytest.mark.parametrize("period", ["day:weekday", "hour:evening"])
@pytest.mark.parametrize("zero_category", ["cold_drinks", "water"])
@pytest.mark.parametrize("other_ratio", [0.5, 1.0, 2.0])
def test_zero_need_ratio_is_the_strongest_effect(period, zero_category, other_ratio):
    other = "water" if zero_category == "cold_drinks" else "cold_drinks"
    priors = ScenarioPriors(need_ratio={period: {zero_category: 0.0, other: other_ratio}})
    effects = compile_scenario(Scenario(), priors)
    categories = {zero_category, other}
    ratio = effects.need_for(categories) if period.startswith("day") else effects.hour_need_for(19, categories)
    assert ratio == 0.0


@pytest.mark.parametrize("period", ["day:weekday", "hour:evening"])
@pytest.mark.parametrize("ratios,expected", [({}, 1.0), ({"water": 2.0}, 2.0),
                                           ({"water": 0.5, "cold_drinks": 3.0}, 3.0),
                                           ({"water": 0.25, "cold_drinks": 2.0}, 0.25)])
def test_positive_and_missing_need_ratios_keep_their_existing_meaning(period, ratios, expected):
    effects = compile_scenario(Scenario(), ScenarioPriors(need_ratio={period: ratios}))
    categories = {"water", "cold_drinks"}
    ratio = effects.need_for(categories) if period.startswith("day") else effects.hour_need_for(19, categories)
    assert ratio == expected


def test_equal_opposing_need_effects_are_stable_across_processes() -> None:
    script = """
import json
from store_emulator.engine.scenario import ScenarioEffects, words_categories

effects = ScenarioEffects(
    need={"cold_drinks": 0.5, "water": 2.0},
    hour_need={"evening": {"cold_drinks": 0.5, "water": 2.0}},
)
categories = words_categories("water")
print(json.dumps([effects.need_for(categories), effects.hour_need_for(19, categories)]))
"""
    outcomes = []
    for hash_seed in ("0", "2"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True, text=True, check=True, timeout=10,
        )
        outcomes.append(json.loads(result.stdout))

    assert outcomes[0] == outcomes[1]
