import json
import os
import subprocess
import sys


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
